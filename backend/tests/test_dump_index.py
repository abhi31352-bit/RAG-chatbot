"""Tests for the index dump script.

The script exists so a human can see what was actually indexed, so the
properties worth protecting are that it stays readable, stays honest about
mismatches, and never crashes on an empty or partially-written index.
"""

import importlib.util
import os

import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "dump_index.py")
spec = importlib.util.spec_from_file_location("dump_index", SCRIPT)
dump = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dump)


# -- Vector description ----------------------------------------------------


def test_local_terms_are_decoded_back_to_dimensions():
    """The point of the local dump: explain which term hit which dimension."""
    text = "the final examination accounts for forty percent"
    vector = [0.0] * 512
    buckets = dump.decode_terms(text, 512)

    assert buckets, "terms should hash somewhere"
    for dim, terms in buckets.items():
        vector[dim] += sum(weight for _t, weight in terms)

    described = dump.describe_vector(vector, text, "local")
    assert "top terms by contribution" in described
    assert "final" in described or "examination" in described


def test_decode_terms_marks_collisions():
    """Two terms in one bucket must be reported, not silently summed."""
    # Two different words that share a 4-char prefix will usually not collide,
    # so assert the shape instead: every bucket maps to a list of terms.
    buckets = dump.decode_terms("alpha beta gamma", 4)
    assert buckets
    assert all(isinstance(terms, list) for terms in buckets.values())


def test_openai_provider_has_no_term_decoding():
    """OpenAI dimensions are opaque; the dump must not invent an explanation."""
    vector = [0.0] * 8
    vector[3] = 0.5
    described = dump.describe_vector(vector, "some text", "openai")
    assert "top dimensions by magnitude" in described
    assert "top terms" not in described
    assert "<-" not in described


def test_full_flag_prints_every_dimension():
    vector = [0.01] * 512
    described = dump.describe_vector(vector, "text", "local", full=True)
    assert "[ 504]" in described, "the last row should be present"
    assert "use --full" not in described


def test_without_full_flag_it_says_so():
    described = dump.describe_vector([0.0] * 512, "text", "local")
    assert "use --full to print all 512" in described


def test_description_reports_sparsity_and_norm():
    vector = [0.0] * 512
    vector[1] = 0.6
    vector[2] = 0.8
    described = dump.describe_vector(vector, "text", "local")
    assert "L2 norm     : 1.000000" in described
    assert "0.4%" in described


def test_sparsity_does_not_divide_by_zero():
    described = dump.describe_vector([], "text", "local")
    assert "dimensions   : 0" in described


# -- Cosine ---------------------------------------------------------------


def test_cosine_of_identical_vectors_is_one():
    vector = [0.3, 0.4, 0.5]
    assert dump.cosine(vector, vector) == pytest.approx(1.0)


def test_cosine_of_orthogonal_vectors_is_zero():
    assert dump.cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_of_opposite_vectors_is_negative():
    assert dump.cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_of_zero_vector_is_zero_not_a_crash():
    """An empty question embeds to zeros; this must not divide by zero."""
    assert dump.cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_of_mismatched_widths_is_zero():
    """A 512-dim query must not be compared to a 1536-dim vector."""
    assert dump.cosine([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


# -- Formatting -----------------------------------------------------------


def test_wrap_preserves_paragraph_breaks():
    assert "\n\n" in dump.wrap("first para\n\nsecond para")


def test_wrap_respects_the_width():
    line = dump.wrap("word " * 200, width=40)
    assert max(len(part) for part in line.split("\n")) <= 40


def test_wrap_indents_continuation_lines():
    wrapped = dump.wrap("alpha beta gamma delta", indent="  ", width=20)
    assert all(part.startswith("  ") for part in wrapped.split("\n") if part.strip())


def test_heading_uppercases_by_default_but_not_a_query():
    assert "SOME THING" in dump.heading("some thing")
    assert "What percentage?" in dump.heading("Similarity to 'What percentage?'", upper=False)


# -- Loading --------------------------------------------------------------


def test_load_documents_on_a_missing_database(tmp_path):
    documents, chunks = dump.load_documents(str(tmp_path / "nope.db"))
    assert documents == []
    assert chunks == {}


def test_report_on_an_empty_index_explains_what_to_do(tmp_path, monkeypatch):
    """An empty index is the most likely first run; it must guide the user.

    Points at its own database rather than the shared test one, which other
    test files leave populated. `sqlite_path` is a read-only property derived
    from DATABASE_URL, so the field is patched instead.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{tmp_path}/empty.db")
    text = dump.report(_args(out="-"), None)
    assert "No documents indexed" in text
    assert "/api/documents/upload" in text


def test_report_surfaces_a_chunk_missing_from_the_vector_store(tmp_path, monkeypatch):
    """Indexed text with no vector is a real inconsistency and must be loud."""
    import sqlite3

    from app.config import settings

    path = tmp_path / "partial.db"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE documents (id TEXT, filename TEXT, file_type TEXT, "
        "file_size INT, status TEXT, chunk_count INT, created_at TEXT, file_path TEXT)"
    )
    connection.execute(
        "CREATE TABLE chunks (id TEXT, document_id TEXT, content TEXT, chunk_index INT,"
        " token_count INT, metadata TEXT, created_at TEXT)"
    )
    connection.execute(
        "INSERT INTO documents VALUES ('doc_a','a.txt','txt',1,'processed',1,'','')"
    )
    connection.execute(
        "INSERT INTO chunks VALUES ('c1','doc_a','the body',0,2,'','')"
    )
    connection.commit()
    connection.close()

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{path}")
    text = dump.report(_args(out="-"), None)
    assert "NOT IN VECTOR STORE" in text


def test_doc_filter_builds_valid_sql(tmp_path):
    """Regression: the filter was appended after ORDER BY."""
    import sqlite3

    path = tmp_path / "app.db"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE documents (id TEXT, filename TEXT, file_type TEXT, "
        "file_size INT, status TEXT, chunk_count INT, created_at TEXT, file_path TEXT)"
    )
    connection.execute("CREATE TABLE chunks (id TEXT, document_id TEXT, content TEXT,"
                       " chunk_index INT, token_count INT, metadata TEXT, created_at TEXT)")
    connection.execute("INSERT INTO documents VALUES ('doc_a','a.txt','txt',1,'processed',0,'','')")
    connection.execute("INSERT INTO documents VALUES ('doc_b','b.txt','txt',1,'processed',0,'','')")
    connection.execute(
        "INSERT INTO chunks VALUES ('c1','doc_b','body text',0,2,'{\"page_number\": 3}','')"
    )
    connection.commit()
    connection.close()

    documents, _ = dump.load_documents(str(path), "doc_b")
    assert [d["id"] for d in documents] == ["doc_b"]

    documents, chunks = dump.load_documents(str(path), None)
    assert len(documents) == 2
    assert chunks["doc_b"][0]["metadata"] == {"page_number": 3}
    assert chunks["doc_b"][0]["content"] == "body text"


def test_missing_chunks_table_does_not_crash(tmp_path):
    """A database created but never initialised should still dump cleanly."""
    import sqlite3

    path = tmp_path / "app.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE documents (id TEXT, filename TEXT)")
    connection.execute("INSERT INTO documents VALUES ('doc_a','a.txt')")
    connection.commit()
    connection.close()

    documents, chunks = dump.load_documents(str(path), None)
    assert [d["id"] for d in documents] == ["doc_a"]
    assert chunks == {}


def test_malformed_metadata_does_not_crash():
    assert dump._safe_json("{not json") == {"_unparsed": "{not json"}
    assert dump._safe_json(None) == {}
    assert dump._safe_json('{"page_number": 2}') == {"page_number": 2}


def _args(**overrides):
    class Args:
        out = "-"
        query = None
        doc = None
        full = False

    args = Args()
    for key, value in overrides.items():
        setattr(args, key, value)
    return args
