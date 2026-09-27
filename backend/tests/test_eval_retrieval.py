"""Tests for the retrieval evaluation script.

The script's whole purpose is to produce a number someone will trust enough to
act on, so the properties worth protecting are that the number is computed
correctly, that a corpus too small to discriminate is reported as meaningless
rather than as a perfect score, and that the answer-key validation fails loudly
on a stale key instead of quietly reporting zeroes.
"""

import importlib.util
import json
import os

import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "eval_retrieval.py")
spec = importlib.util.spec_from_file_location("eval_retrieval", SCRIPT)
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)

KEY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "samples", "eval", "answer_key.json"
)


def make_row(rank=None, answerable=False, difficulty="verbatim", expected="a.txt"):
    return {
        "question": "q",
        "difficulty": difficulty,
        "expected": expected,
        "rank": rank,
        "similarity": 0.1,
        "top_filename": "b.txt" if rank is None else expected,
        "answerable": answerable,
        "hit": rank is not None,
        "missing": [],
    }


# -- Text normalisation ----------------------------------------------------


def test_normalise_collapses_wrapped_lines():
    # The corpus is hard-wrapped, so an answer straddling a newline is stored
    # as "worth 25\npoints". Without flattening, the keyword "25 points" is
    # reported missing on a chunk that plainly contains it, and the failure is
    # indistinguishable from a real retrieval miss.
    assert ev.normalise("worth 25\npoints each") == "worth 25 points each"
    assert ev.normalise("worth 25\r\npoints") == "worth 25 points"


def test_normalise_is_case_insensitive():
    assert ev.normalise("There is no required GPU") == "there is no required gpu"


def test_normalise_survives_runs_of_whitespace():
    assert ev.normalise("a  \t b\n\n c") == "a b c"


# -- Scoring ---------------------------------------------------------------


def test_summarise_reports_hit_rate():
    rows = [make_row(rank=1), make_row(rank=1), make_row(rank=3), make_row(rank=None)]
    summary = ev.summarise(rows, "all")

    assert summary["n"] == 4
    assert summary["hit"] == 0.75
    assert summary["mrr"] == pytest.approx((1 + 1 + 1 / 3) / 4)
    assert summary["answerable"] == 0.0


def test_summarise_gives_full_mrr_when_always_first():
    assert ev.summarise([make_row(rank=1)] * 3, "all")["mrr"] == 1.0


def test_summarise_handles_a_total_miss_without_dividing_by_zero():
    # A retriever that retrieved nothing still has to produce a report.
    summary = ev.summarise([make_row(rank=None)] * 2, "all")
    assert summary["hit"] == 0.0
    assert summary["mrr"] == 0.0


def test_summarise_of_nothing_is_none():
    assert ev.summarise([], "all") is None


# -- The small-corpus guard ------------------------------------------------


def test_corpus_larger_than_top_k_is_meaningful():
    assert ev.check_corpus_is_meaningful(17, 5) is True


def test_corpus_the_size_of_top_k_is_reported_as_meaningless(capsys):
    # The trap this exists for: two chunks with top_k of 5 returns everything
    # for every question, so hit@k is 100% by construction and means nothing.
    assert ev.check_corpus_is_meaningful(2, 5) is False
    out = capsys.readouterr().out
    assert "WARNING" in out
    assert "measures nothing" in out


def test_corpus_smaller_than_top_k_is_reported_as_meaningless(capsys):
    assert ev.check_corpus_is_meaningful(1, 5) is False
    assert "WARNING" in capsys.readouterr().out


# -- Filename extraction ---------------------------------------------------


def test_filename_is_read_from_the_top_level_field():
    assert ev._filename_of({"filename": "a.txt"}) == "a.txt"


def test_filename_falls_back_to_metadata():
    assert ev._filename_of({"metadata": {"filename": "b.txt"}}) == "b.txt"


def test_filename_of_nothing_is_none():
    assert ev._filename_of(None) is None


# -- Database path ---------------------------------------------------------


def test_database_file_resolves_a_relative_url():
    # There is no dedicated database path setting, only a URL, so the path is
    # parsed back out. Getting this wrong deletes the wrong file.
    path = ev.database_file("sqlite+aiosqlite:///./data/app.db")
    assert path is not None
    assert path.endswith("app.db")
    # Relative URLs anchor to backend/, not to the current directory, so the
    # script cannot delete a different file than the app opens.
    assert os.path.isabs(path)
    assert path == ev.resolve_path("./data/app.db")


def test_database_file_keeps_an_absolute_url_absolute():
    absolute = "/tmp/elsewhere/app.db"
    assert ev.database_file(f"sqlite+aiosqlite:///{absolute}") == absolute


def test_database_file_defaults_to_the_configured_url():
    assert ev.database_file() == ev.database_file(ev.settings.async_database_url)


def test_database_file_ignores_an_in_memory_url():
    assert ev.database_file("sqlite+aiosqlite:///:memory:") is None


def test_database_file_ignores_a_url_with_no_path():
    assert ev.database_file("") is None


# -- The shipped answer key ------------------------------------------------


def test_answer_key_is_valid_json():
    with open(KEY_PATH, encoding="utf-8") as handle:
        key = json.load(handle)
    assert key["questions"]


def test_answer_key_declares_a_difficulty_for_every_question():
    with open(KEY_PATH, encoding="utf-8") as handle:
        key = json.load(handle)
    for case in key["questions"]:
        assert case.get("difficulty") in {"verbatim", "paraphrased"}, case["question"]


def test_answer_key_every_question_names_a_document_and_keywords():
    with open(KEY_PATH, encoding="utf-8") as handle:
        key = json.load(handle)
    for case in key["questions"]:
        assert case.get("expect_document"), case["question"]
        # Keywords are what make the strict "answerable" metric work at all;
        # a question without them silently passes that check.
        assert case.get("expect_keywords"), case["question"]


def test_answer_key_keywords_actually_appear_in_their_document():
    """A stale key would report a perfect retriever as failing everything."""
    with open(KEY_PATH, encoding="utf-8") as handle:
        key = json.load(handle)

    corpus_dir = os.path.join(
        os.path.dirname(__file__), "..", key.get("corpus", "samples/eval/corpus")
    )
    for case in key["questions"]:
        path = os.path.join(corpus_dir, case["expect_document"])
        assert os.path.exists(path), f"missing document for {case['question']!r}"
        with open(path, encoding="utf-8") as handle:
            body = ev.normalise(handle.read())
        assert any(
            ev.normalise(k) in body for k in case["expect_keywords"]
        ), f"{case['expect_keywords']!r} not found in {case['expect_document']}"


def test_corpus_holds_more_chunks_than_top_k():
    """Otherwise every reported rate is 100% for free."""
    from app.config import settings
    from app.utils.text_processor import get_text_processor

    processor = get_text_processor()
    corpus_dir = os.path.join(os.path.dirname(__file__), "..", "samples", "eval", "corpus")
    total = 0
    for name in sorted(os.listdir(corpus_dir)):
        path = os.path.join(corpus_dir, name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as handle:
                total += len(
                    processor.chunk_text(handle.read(), settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
                )

    assert total > settings.TOP_K_RETRIEVAL, (
        f"corpus is {total} chunks against top_k {settings.TOP_K_RETRIEVAL}; "
        "retrieval would return everything and measure nothing"
    )
