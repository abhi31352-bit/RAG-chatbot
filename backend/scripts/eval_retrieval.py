"""Measure retrieval quality against a labelled question set.

Retrieval is the half of the pipeline that decides *which* text the generator
gets to quote, and it is the half that is easy to fool yourself about. A
system that returns the whole index looks perfect on a two-chunk demo corpus
and falls apart on a real one, because `top_k` never has to exclude anything.
So this script refuses to report a hit rate that means nothing: it checks that
the index holds more chunks than `top_k` and warns loudly when it does not.

Three numbers are reported, from loosest to strictest:

  hit@k        the expected document appears anywhere in the top k. This is
               the question "did we retrieve the right file".
  MRR          mean reciprocal rank of the expected document. Distinguishes
               "found it first try" from "found it last", which hit@k alone
               flattens into a single bit.
  answerable   the expected strings appear in the *top* chunk. This is the
               strict one: the right document at rank 4 is no use to a
               generator that can only read the chunk at rank 1.

Results are split by `difficulty` in the answer key. Verbatim questions reuse
the document's own vocabulary; paraphrased ones deliberately do not. The local
provider is a hashed bag of words, so it has no synonym knowledge by
construction, and the gap between the two columns is a measurement of that
limitation rather than a vague sense that it exists.

Usage::

    ./venv/bin/python scripts/eval_retrieval.py --index     # reset + index corpus, then evaluate
    ./venv/bin/python scripts/eval_retrieval.py             # evaluate current index
    ./venv/bin/python scripts/eval_retrieval.py --top-k 3 --verbose

`--index` wipes the database and the vector store first, because the demo
documents must not pollute the corpus: a stray extra document changes the
candidate pool and every score with it.
"""

import argparse
import asyncio
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import resolve_path, settings  # noqa: E402
from app.models.database import async_session, engine  # noqa: E402
from app.rag.retriever import Retriever  # noqa: E402
from app.services.document_service import DocumentService  # noqa: E402

WIDTH = 78

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)

DEFAULT_KEY = os.path.join(BACKEND_DIR, "samples", "eval", "answer_key.json")


def rule(char="="):
    return char * WIDTH


def heading(title):
    print()
    print(rule())
    print(title.center(WIDTH))
    print(rule())


# --------------------------------------------------------------------------
# Index management
# --------------------------------------------------------------------------


def database_file(url=None):
    """Absolute path of the SQLite file, derived from DATABASE_URL.

    There is no dedicated path setting for the database -- only the URL -- so
    the path is parsed back out of it. `resolve_path` applies the same
    anchoring the application uses, so a relative URL in `.env` resolves to the
    same file the app would open.

    `url` is injectable because `settings.async_database_url` is a read-only
    property and cannot be substituted in a test. The default is selected with
    an explicit `is None` check: `url or settings...` would treat an empty
    string as "not supplied" and silently fall back to the configured URL.
    """
    if url is None:
        url = settings.async_database_url
    _, separator, tail = url.partition("///")
    if not separator or not tail:
        return None
    if not tail.startswith("/") and not tail.startswith("."):
        # A non-path sqlite URL such as :memory: has nothing to delete.
        return None
    return resolve_path(tail)


def reset_data_dir():
    """Delete the database, the vector store and any stored uploads."""
    targets = [database_file(), settings.chroma_path, settings.upload_path]
    for path in targets:
        if not path or not os.path.exists(path):
            continue
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            # The engine may still hold the file open; on POSIX that is fine.
            os.remove(path)


async def index_corpus(corpus_dir):
    """Load every document in `corpus_dir` through the real ingestion path."""
    from app.models.database import Base

    service = DocumentService()
    indexed = []
    paths = [
        os.path.join(corpus_dir, name)
        for name in sorted(os.listdir(corpus_dir))
        if os.path.isfile(os.path.join(corpus_dir, name))
    ]
    if not paths:
        raise SystemExit(f"No files found in corpus directory: {corpus_dir}")

    async with async_session() as session:
        # Tables must exist before the first insert. The app normally does this
        # on startup, and this script deliberately does not start the app.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        for path in paths:
            with open(path, "rb") as handle:
                contents = handle.read()
            document = await service.save_document(
                session,
                filename=os.path.basename(path),
                file_type=os.path.splitext(path)[1].lstrip("."),
                file_size=len(contents),
                contents=contents,
            )
            await service.process_document(session, document, contents)
            await session.refresh(document)
            indexed.append((os.path.basename(path), document.chunk_count))
            print(
                f"  indexed {os.path.basename(path):34s} "
                f"{document.chunk_count} chunk(s)"
            )

    return indexed


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------


def load_key(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def normalise(text):
    """Lowercase and collapse whitespace so phrases survive line wrapping.

    The corpus is plain text wrapped at 80 columns, so a phrase written across
    a line break is stored in the chunk as "worth 25\\npoints each". Matching
    that against the literal string "25 points" fails even though the answer is
    plainly present, and the failure is indistinguishable from a genuine
    retrieval miss. Whitespace has to be flattened on both sides before
    comparing, or every answer that straddles a newline reads as missing.
    """
    return " ".join(text.lower().split())


async def evaluate(questions, top_k, verbose):
    retriever = Retriever()
    rows = []

    for case in questions:
        hits = await retriever.retrieve(case["question"], top_k=top_k)
        expected = case["expect_document"]

        rank = None
        for position, hit in enumerate(hits, start=1):
            if _filename_of(hit) == expected:
                rank = position
                break

        top_hit = hits[0] if hits else None
        top_text = normalise(top_hit.get("content", "") if top_hit else "")
        keywords = [normalise(k) for k in case.get("expect_keywords", [])]
        answerable = bool(keywords) and any(k in top_text for k in keywords)

        rows.append(
            {
                "question": case["question"],
                "difficulty": case.get("difficulty", "unlabelled"),
                "expected": expected,
                "rank": rank,
                "similarity": top_hit.get("similarity") if top_hit else 0.0,
                "top_filename": _filename_of(top_hit),
                "answerable": answerable,
                "hit": rank is not None,
                "missing": [k for k in keywords if k not in top_text],            }
        )

        if verbose:
            mark = "ok " if rows[-1]["hit"] else "MISS"
            got = f"rank {rank}" if rank else "not retrieved"
            print(f"  [{mark}] {case['difficulty']:11s} {got:13s} {case['question'][:52]}")

    return rows


def _filename_of(hit):
    if not hit:
        return None
    if hit.get("filename"):
        return hit["filename"]
    return (hit.get("metadata") or {}).get("filename")


def summarise(rows, label):
    total = len(rows)
    if total == 0:
        return None

    hits = [r for r in rows if r["hit"]]
    answerable = [r for r in rows if r["answerable"]]
    reciprocal = sum(1.0 / r["rank"] for r in hits) / total if hits else 0.0

    return {
        "label": label,
        "n": total,
        "hit": len(hits) / total,
        "mrr": reciprocal,
        "answerable": len(answerable) / total,
    }


def render_table(stats):
    print()
    print(f"  {'group':<14}{'n':>4}{'hit@k':>9}{'MRR':>8}{'answerable':>13}")
    print(f"  {rule('-')[:WIDTH - 4]}")
    for entry in stats:
        if entry is None:
            continue
        print(
            f"  {entry['label']:<14}{entry['n']:>4}"
            f"{entry['hit'] * 100:>8.0f}%{entry['mrr']:>8.2f}"
            f"{entry['answerable'] * 100:>12.0f}%"
        )


def render_misses(rows, top_k):
    misses = [r for r in rows if not r["hit"]]
    if not misses:
        print("\n  Every expected document was retrieved.")
        return

    print(f"\n  {len(misses)} question(s) where the right document was not in the top {top_k}:")
    for row in misses:
        print(f"    - [{row['difficulty']}] {row['question']}")
        print(f"        expected {row['expected']}, got {row['top_filename']} "
              f"(sim {row['similarity']:.3f})")

    # A document that is retrieved but at a low rank, or retrieved at rank 1
    # without the answer text, is a different failure from being absent, and
    # the two need different fixes.
    degraded = [r for r in rows if r["hit"] and not r["answerable"]]
    if degraded:
        print(f"\n  {len(degraded)} question(s) retrieved the right document but the top "
              f"chunk did not contain the answer:")
        for row in degraded:
            print(f"    - [{row['difficulty']}] {row['question'][:60]}")
            print(f"        rank {row['rank']}, missing: {', '.join(row['missing']) or '(none)'}")


def check_corpus_is_meaningful(total_chunks, top_k):
    """A hit rate over a corpus smaller than top_k is not a measurement."""
    if total_chunks > top_k:
        return True
    print()
    print(f"  WARNING: the index holds {total_chunks} chunk(s) and top_k is {top_k}.")
    print("  Retrieval returns the entire index for every question, so hit@k is")
    print("  guaranteed to be 100% and measures nothing. Index more documents before")
    print("  drawing any conclusion from these numbers.")
    return False


async def main_async(args):
    key = load_key(args.key)
    corpus_dir = args.corpus or os.path.join(BACKEND_DIR, key.get("corpus", "samples/eval/corpus"))
    questions = key["questions"]

    if args.index:
        heading("RESETTING AND INDEXING CORPUS")
        reset_data_dir()
        print(f"  corpus: {corpus_dir}\n")
        indexed = await index_corpus(corpus_dir)
        print(f"\n  {len(indexed)} document(s) indexed.")

    from app.services.embedding_service import get_embedding_service

    stats = await get_embedding_service().get_stats()

    heading("CORPUS")
    print(f"  corpus          : {corpus_dir}")
    print(f"  questions       : {len(questions)}")
    print(f"  top_k           : {args.top_k}")
    print(f"  indexed chunks  : {stats['total_chunks']}")
    print(f"  embedding model : {stats['embedding_model']}")
    print(f"  indexed with    : {stats['indexed_with']}")

    meaningful = check_corpus_is_meaningful(stats["total_chunks"], args.top_k)

    heading("RESULTS")
    rows = await evaluate(questions, args.top_k, args.verbose)

    table = [summarise(rows, "all")]
    for difficulty in sorted({r["difficulty"] for r in rows}):
        table.append(summarise([r for r in rows if r["difficulty"] == difficulty], difficulty))
    render_table(table)

    render_misses(rows, args.top_k)

    heading("READING THIS")
    print("  hit@k       right document somewhere in the top k")
    print("  MRR         how high up it was, 1.00 meaning always first")
    print("  answerable  the answer text was in the chunk at rank 1")
    print()
    print("  The gap between 'verbatim' and 'paraphrased' is the thing to watch.")
    print("  A large drop means retrieval is matching on shared vocabulary rather")
    print("  than on meaning, which is the expected behaviour of a hashed bag of")
    print("  words and cannot be fixed by tuning top_k.")

    if args.min_answerable is not None and meaningful:
        overall = summarise(rows, "all")
        if overall["answerable"] < args.min_answerable:
            print()
            print(
                f"  FAIL: answerable rate {overall['answerable'] * 100:.0f}% "
                f"is below the required {args.min_answerable * 100:.0f}%"
            )
            return 1

    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key", default=DEFAULT_KEY, help="answer key JSON")
    parser.add_argument("--corpus", help="override the corpus directory")
    parser.add_argument("--top-k", type=int, default=settings.TOP_K_RETRIEVAL)
    parser.add_argument("--index", action="store_true", help="reset and index the corpus first")
    parser.add_argument("--verbose", action="store_true", help="print a line per question")
    parser.add_argument(
        "--min-answerable",
        type=float,
        help="exit non-zero if the answerable rate falls below this fraction",
    )
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(main_async(args))
    finally:
        loop.close()


if __name__ == "__main__":
    sys.exit(main())
