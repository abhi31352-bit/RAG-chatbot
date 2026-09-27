"""Write a human-readable dump of the index: chunks and their embeddings.

The vector store keeps embeddings as opaque float arrays, which makes it hard
to see what was actually indexed or why a query matched what it matched. This
script writes a plain text report covering both, so the index can be inspected
without writing any code.

Usage::

    ./venv/bin/python scripts/dump_index.py                    # data/index_dump.txt
    ./venv/bin/python scripts/dump_index.py --out -            # stdout
    ./venv/bin/python scripts/dump_index.py --query "exam?"    # + similarity ranking
    ./venv/bin/python scripts/dump_index.py --full             # every dimension
    ./venv/bin/python scripts/dump_index.py --doc doc_abc123   # one document

For the local provider the report also decodes each vector back into the terms
that produced it, which is what makes a surprising match explainable. The
OpenAI provider has no such structure, so only its summary is shown.
"""

import argparse
import json
import math
import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings  # noqa: E402
from app.services.embedding_service import (  # noqa: E402
    EmbeddingService,
    get_chroma_collection,
)

WIDTH = 78
PREVIEW_DIMS = 24
TOP_DIMS = 12


def rule(char="="):
    return char * WIDTH


def heading(title, upper=True):
    # A query is passed through verbatim: uppercasing it would misrepresent
    # what was actually asked.
    text = title.upper() if upper else title
    return "\n".join([rule(), text.center(WIDTH), rule()])


def wrap(text, indent="  ", width=WIDTH - 2):
    """Greedy word wrap that keeps existing newlines."""
    out = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            out.append("")
            continue
        line = ""
        for word in paragraph.split():
            if not line:
                line = indent + word
            elif len(line) + 1 + len(word) <= width:
                line += " " + word
            else:
                out.append(line)
                line = indent + word
        if line:
            out.append(line)
    return "\n".join(out)


def vector_norm(vector):
    return math.sqrt(sum(v * v for v in vector))


def decode_terms(text, dim):
    """Map each term in `text` to the dimension it hashes into.

    Returns ``{dimension: [(term, signed_weight), ...]}``. Only meaningful for
    the local provider -- OpenAI dimensions have no such correspondence.
    """
    import hashlib
    import re
    from collections import Counter

    words = re.findall(r"[a-z0-9]+", text.lower())
    features = Counter(words)
    for i in range(len(words) - 1):
        features[f"{words[i]}_{words[i + 1]}"] += 1

    buckets = {}
    if dim <= 0:
        return buckets
    for term, count in features.items():
        digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] & 1 else -1.0
        buckets.setdefault(index, []).append((term, sign * (1.0 + math.log(count))))
    return buckets


def describe_vector(vector, content, provider, full=False, indent="    "):
    """Render one embedding: shape, then either decoded terms or raw values."""
    dim = len(vector)
    non_zero = sum(1 for v in vector if v != 0.0)
    norm = vector_norm(vector)

    # A zero-width vector is possible if a provider ever returns one, and the
    # sparsity percentage would otherwise divide by zero.
    sparse = f"{100.0 * non_zero / dim:.1f}%" if dim else "n/a"
    lines = [
        f"{indent}dimensions   : {dim}",
        f"{indent}non-zero     : {non_zero} ({sparse} sparse)",
        f"{indent}L2 norm     : {norm:.6f}",
    ]

    if provider == "local":
        buckets = decode_terms(content, dim)
        # Rank by the stored vector's own magnitude so the report describes the
        # data on disk, not a re-derivation of it.
        ranked = sorted(
            buckets.items(), key=lambda row: abs(vector[row[0]]), reverse=True
        )[:TOP_DIMS]
        if ranked:
            lines.append(f"{indent}top terms by contribution:")
            for i, terms in ranked:
                shown = ", ".join(t for t, _w in sorted(terms))
                collisions = " +collision" if len(terms) > 1 else ""
                lines.append(
                    f"{indent}  dim {i:>4} = {vector[i]:+.4f}  <- {shown}{collisions}"
                )
    else:
        ranked = sorted(range(dim), key=lambda i: abs(vector[i]), reverse=True)[
            :TOP_DIMS
        ]
        if ranked:
            lines.append(f"{indent}top dimensions by magnitude:")
            for i in ranked:
                lines.append(f"{indent}  dim {i:>4} = {vector[i]:+.4f}")

    if full:
        lines.append(f"{indent}full vector:")
        for start in range(0, dim, 8):
            row = vector[start : start + 8]
            lines.append(
                f"{indent}  [{start:>4}] "
                + " ".join(f"{v:+.5f}" for v in row)
            )
    else:
        preview = vector[:PREVIEW_DIMS]
        lines.append(
            f"{indent}first {len(preview)} dims: ["
            + ", ".join(f"{v:+.4f}" for v in preview)
            + (" ...]" if dim > len(preview) else "]")
        )
        lines.append(f"{indent}  (use --full to print all {dim})")

    return "\n".join(line for line in lines if line)


def load_documents(sqlite_path, only=None):
    """Read documents and chunk text from SQLite, the source of truth for text."""
    if not os.path.exists(sqlite_path):
        return [], {}
    connection = sqlite3.connect(sqlite_path)
    connection.row_factory = sqlite3.Row
    try:
        # WHERE has to precede ORDER BY, so the filter is spliced in rather than
        # appended to a fixed query string. A database with a partial schema
        # should still dump, so a missing created_at falls back to unordered.
        query = "SELECT * FROM documents"
        params = ()
        if only:
            query += " WHERE id = ?"
            params = (only,)
        try:
            documents = [dict(r) for r in connection.execute(query + " ORDER BY created_at", params)]
        except sqlite3.OperationalError:
            documents = [dict(r) for r in connection.execute(query, params)]

        placeholders = ",".join("?" * len(documents))
        chunks = {}
        if documents:
            try:
                rows = connection.execute(
                    f"SELECT * FROM chunks WHERE document_id IN ({placeholders}) "
                    "ORDER BY document_id, chunk_index",
                    [d["id"] for d in documents],
                )
            except sqlite3.OperationalError:
                # A database whose tables were never created should still
                # produce a readable report rather than a traceback.
                return documents, chunks
            for row in rows:
                record = dict(row)
                record["metadata"] = _safe_json(record.get("metadata"))
                chunks.setdefault(record["document_id"], []).append(record)
        return documents, chunks
    finally:
        connection.close()


def _safe_json(raw):
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {"_unparsed": raw}


def load_vectors(only=None):
    """Read every stored embedding out of Chroma, keyed by vector id."""
    collection = get_chroma_collection()
    if collection.count() == 0:
        return {}, 0
    raw = collection.get(include=["embeddings", "documents", "metadatas"])
    vectors = {}
    for i, vector_id in enumerate(raw["ids"]):
        vectors[vector_id] = {
            "embedding": list(raw["embeddings"][i]),
            "document": (raw["documents"] or [None] * len(raw["ids"]))[i],
            "metadata": (raw["metadatas"] or [{}] * len(raw["ids"]))[i],
        }
    return vectors, len(vectors)


def report(args, query_vector=None):
    info = EmbeddingService._read_index_info()
    provider = info.get("embedding_provider", "unknown")
    documents, chunks = load_documents(settings.sqlite_path, args.doc)
    vectors, vector_count = load_vectors(args.doc)

    out = []
    add = out.append

    add(rule())
    add("RAG CHATBOT - INDEX DUMP".center(WIDTH))
    add(rule())
    add(f"  generated        : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    add(f"  database         : {settings.sqlite_path}")
    add(f"  vector store     : {settings.chroma_path}")
    add("")
    add(heading("Index configuration"))
    add(f"  provider         : {info.get('embedding_provider', '(none)')}")
    add(f"  model            : {info.get('embedding_model', '(none)')}")
    add(f"  dimension        : {info.get('embedding_dimension', '(none)')}")
    add(f"  documents        : {len(documents)}")
    add(f"  chunks in sqlite : {sum(len(c) for c in chunks.values())}")
    add(f"  vectors in chroma: {vector_count}")

    if not documents:
        add("")
        add("  No documents indexed. Start the server and POST a file to")
        add("  /api/documents/upload, then run this again.")
        return "\n".join(out)

    add(heading("Documents"))
    for number, document in enumerate(documents, 1):
        size = document.get("file_size") or 0
        add(f"  [{number}] {document['id']}")
        add(f"      filename     : {document.get('filename')}")
        add(f"      type / size  : {document.get('file_type')} / {size} bytes")
        add(f"      status       : {document.get('status')}")
        add(f"      chunk_count  : {document.get('chunk_count')}")
        add(f"      created_at   : {document.get('created_at')}")
        add(f"      stored file  : {document.get('file_path') or '(none)'}")
        stored = (
            "present" if document.get("file_path") and os.path.exists(document["file_path"]) else "MISSING"
        )
        add(f"      on disk      : {stored}")
        add("")

    add(heading("Chunks and embeddings"))
    for document in documents:
        add("")
        add(f"### {document['id']}  ({document.get('filename')})")
        for record in chunks.get(document["id"], []):
            vector_id = f"{document['id']}::chunk_{record['chunk_index']}"
            entry = vectors.get(vector_id)
            metadata = record.get("metadata") or {}
            page = metadata.get("page_number")
            content = record.get("content") or ""

            add("")
            add(f"  -- chunk #{record['chunk_index']} " + "-" * (WIDTH - 16))
            add(f"     vector id     : {vector_id}")
            add(f"     page_number   : {page if page is not None else '(none)'}")
            add(f"     characters    : {len(content)}")
            add(f"     token_count   : {record.get('token_count')}")
            add(f"     created_at    : {record.get('created_at')}")
            add("")
            add(wrap(content))

            add("")
            if entry is None:
                add("    EMBEDDING: *** NOT IN VECTOR STORE (text indexed but not embedded) ***")
                continue
            add("    EMBEDDING:")
            add(describe_vector(entry["embedding"], content, provider, args.full))
            if entry.get("document") is not None and entry["document"] != content:
                add("    note: vector-store text differs from the sqlite text")

    if args.query and query_vector is not None:
        add(heading(f"Similarity to query: {args.query!r}", upper=False))
        add("  Recomputed with the active provider, so these are the scores the")
        add("  chat pipeline sees. Negative means opposing hash signs.")
        add("")
        rows = []
        for vector_id, entry in vectors.items():
            if args.doc and not vector_id.startswith(args.doc):
                continue
            rows.append((cosine(query_vector, entry["embedding"]), vector_id, entry))
        rows.sort(reverse=True, key=lambda row: row[0])
        for score, vector_id, entry in rows:
            content = entry.get("document") or ""
            add(f"  {score:+.4f}  {vector_id}")
            add(wrap(content[:180] + ("..." if len(content) > 180 else ""), indent="          "))
            add("")

    return "\n".join(out)


def cosine(a, b):
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = vector_norm(a), vector_norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="index_dump.txt", help="output file, or - for stdout")
    parser.add_argument("--query", help="rank chunks by similarity to this question")
    parser.add_argument("--doc", help="restrict to one document id")
    parser.add_argument("--full", action="store_true", help="print every dimension")
    args = parser.parse_args()

    query_vector = None
    if args.query:
        import asyncio

        from app.services.embedding_service import get_embedding_service

        query_vector = asyncio.get_event_loop().run_until_complete(
            get_embedding_service().embed_query(args.query)
        )

    text = report(args, query_vector)

    if args.out == "-":
        print(text)
    else:
        path = os.path.abspath(args.out)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print(f"Wrote {path} ({len(text):,} chars)")


if __name__ == "__main__":
    main()
