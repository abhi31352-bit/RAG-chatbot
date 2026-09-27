# Retrieval evaluation corpus

A labelled question set for measuring **retrieval** — which chunks come back
for a question — separately from **answering**, which decides what the
generator quotes from those chunks.

Run it with:

```bash
cd backend
./venv/bin/python scripts/eval_retrieval.py --index     # reset + index, then evaluate
./venv/bin/python scripts/eval_retrieval.py             # evaluate the current index
./venv/bin/python scripts/eval_retrieval.py --top-k 3 --verbose
```

`--index` wipes the database and the vector store first. The demo documents
must not pollute the corpus: one extra document changes the candidate pool and
every score with it.

## Why this exists

Testing retrieval against the two sample documents measures nothing. They are
129 tokens each, `CHUNK_SIZE` is 500 tokens, so each is a single chunk, and
`TOP_K_RETRIEVAL` is 5. Retrieval therefore returns the entire index for every
question, including "what is the capital of France" — hit@5 is 100% by
construction. A retriever that returns everything scores the same as a good one.

The script refuses to report that as a result. If the index holds no more
chunks than `top_k`, it prints a warning saying the numbers measure nothing.

This corpus produces **17 chunks across 8 documents**, so `top_k=5` genuinely
has to exclude 12 of them.

## The corpus

| Document | Chunks | Topic |
|----------|--------|-------|
| `01_grading.txt` | 2 | Grade weights, letter scale, late work, exemptions |
| `02_staff.txt` | 2 | Instructor, TAs, office hours, how to get an answer |
| `03_deadlines.txt` | 2 | Project milestones, submission mechanics |
| `04_assessment_mechanics.txt` | 2 | Marking conventions, regrades, exam conduct |
| `05_ml_concepts.md` | 3 | Weeks 1–7 content: regression, regularisation, ensembles |
| `06_policies.txt` | 2 | Integrity, AI-assistant disclosure, accommodations |
| `07_resources.txt` | 2 | Software, textbooks, datasets, computing |
| `08_schedule.txt` | 2 | Week-by-week schedule and examinations |

The documents deliberately overlap in vocabulary — several discuss deadlines,
several discuss marking — so retrieval has something to discriminate. They are
synthetic and factually empty; they exist to be retrieved, not to be true.

## The answer key

`answer_key.json` holds 27 questions. Each names the document that should be
retrieved and the strings that prove the answer actually landed in the top
chunk. `expect_keywords` are alternatives — any one matching counts.

`difficulty` is the field that matters:

- **`verbatim`** (16) reuses the document's own words. "When is the midterm
  examination and what does it cover?"
- **`paraphrased`** (11) deliberately avoids them. "How much time do I get for
  the last test of the term?" — the document says "final examination", never
  "test".

The gap between the two columns is the measurement. The local provider is a
hashed bag of words with no synonym knowledge by construction, so a large drop
is not a bug to be fixed by tuning `top_k`; it is the shape of the thing.

## The three numbers

| Metric | Question it answers |
|--------|--------------------|
| `hit@k` | Did we retrieve the right document at all? |
| `MRR` | How near the top was it? `1.00` means always first. |
| `answerable` | Was the answer text in the chunk at **rank 1**? |

`answerable` is the strict one and the most useful. The right document at
rank 4 is no use to a generator that reads the top chunk, so `hit@k` and
`answerable` measure genuinely different things.

## Measured baseline

Local provider, `local-hash-2048`, `top_k=5`, 17 chunks, 27 questions:

| Group | n | hit@5 | MRR | answerable |
|-------|---|-------|-----|------------|
| all | 27 | 85% | 0.74 | 59% |
| verbatim | 16 | **100%** | 0.91 | 75% |
| paraphrased | 11 | **64%** | 0.50 | 36% |

**Verbatim retrieval is effectively perfect; paraphrased is not.** Every one of
the four document-level misses is a paraphrased question.

The misses are all synonym failures, not near-misses on arithmetic or ranking:

| Question | Expected | Retrieved instead |
|----------|----------|-------------------|
| "What do I lose if I hand work in after the deadline?" | `01_grading.txt` | `04_assessment_mechanics.txt` |
| "When do I need to hand in the opening part of my group assignment?" | `03_deadlines.txt` | `02_staff.txt` |
| "Do I have to buy a book for this class?" | `07_resources.txt` | `04_assessment_mechanics.txt` |
| "How much time do I get for the last test of the term?" | `08_schedule.txt` | `04_assessment_mechanics.txt` |

`04_assessment_mechanics.txt` wins all four because it is about examinations
and marking, so it shares more surface words with any question about "work",
"hand in", or "book" than the intended document does.

There is also a distinct, sharper failure the `answerable` column catches:
the right document retrieved, but the wrong chunk inside it. For *"Do I need a
GPU for the assignments?"*, `07_resources.txt` is returned — and the chunk
containing "the course does not require a GPU" comes back **third**, behind a
different chunk of the same document. Raising `top_k` would fix that one;
no amount of `top_k` fixes the four above.

## Reading a regression

Run before and after a change and compare the two rows that matter:

- `verbatim` should stay at 100% hit. A drop means you broke lexical matching,
  which is the capability the current provider actually has.
- `paraphrased` is the headroom. It is the number a real embedding model would
  move, and it cannot move while the embedder is a hash of tokens.

`--min-answerable 0.5` makes the script exit non-zero below a threshold, for
use in a check that should fail the build.
