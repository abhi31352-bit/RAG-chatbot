# Sample documents

Documents used to exercise the system. They are **not** needed to run the app —
upload whatever you like instead. They live here so that a fresh checkout has
something to index without hunting for files.

## Where the demo documents live

The walkthrough content is **not** here. It is in `demo/sample-documents/` at the
repository root, alongside the demo script that uses it:

| File | Chunks | Contains |
|------|--------|----------|
| `syllabus.txt` | 1 | Grading breakdown, late policy, staff, project deadlines |
| `lecture-notes-week1.md` | 3 | Linear regression, gradient descent, bias-variance tradeoff |
| `course-schedule.md` | 1 | Week-by-week topics, assessment dates, office hours |

The three are deliberately disjoint. An earlier version had `lecture.md`
duplicating the syllabus word for word, which made it impossible to show the
most interesting property of the system -- that a question about grading
retrieves the syllabus while a question about gradient descent retrieves the
lecture notes, each answer citing only the document it came from.

```bash
for f in demo/sample-documents/*; do
  curl -X POST http://localhost:8000/api/documents/upload -F "file=@$f"
done
```

Two notes on what to expect:

- The suggested questions in the chat UI are drawn from `demo/sample-documents/`.
  In offline mode the generator matches question terms against sentences
  literally, so a question phrased with vocabulary the documents never use still
  falls back: "What are the assessment weights?" retrieves the grading chunk
  correctly and then finds nothing to quote, because the syllabus says "accounts
  for 40 percent of the course grade" and never says "weights". The same goes
  for "What grading policy applies to late submissions?" — "late" is present,
  "policy" and "submissions" are not. With a real model this does not happen;
  the limitation is in the offline responder, not in retrieval.
- Upload `fixtures/` separately from the demo set. Filler sentences from
  `long.pdf` match broad questions and dilute the answers.

## `fixtures/` — coverage, not content

These exist to exercise code paths that clean documents do not reach. Chunk
counts are at the default `CHUNK_SIZE=500` **tokens** (not characters), which is
why the character counts and chunk counts are not proportional.

| File | Chars | Tokens | Chunks | Pages | Exercises |
|------|-------|--------|--------|-------|-----------|
| `lab_schedule.docx` | 658 | 142 | 1 | — | The only DOCX in the repo, so the `python-docx` parser is covered |
| `long.pdf` | 39,694 | 2,839 | 7 | 8 | Multi-chunk *and* multi-page, so per-page attribution is checked across chunks |
| `long.txt` | 15,680 | 2,656 | 6 | — | Multi-chunk splitting where page numbers must stay absent |
| `multi.pdf` | 29,770 | 443 | 1 | 6 | One chunk spanning six pages — the case where "a chunk reports the page it starts on" matters |
| `multi.txt` | 1,014 | 216 | 1 | — | Page-*like* prose ("Page 1 content…") with no real pages, so numbering must stay unknown rather than be parsed from the text |
| `src.txt` | 550 | 124 | 1 | — | A near-duplicate of the grading and staff passages in `demo/sample-documents/syllabus.txt`, so the same answer can surface from two documents |

`long.pdf` and `long.txt` contain `PAGE n MARKER` text so page attribution can be
checked. A chunk reports the page it *starts* on, so a gap in page numbers
between consecutive chunks is expected, not a bug.

`multi.pdf` looks wrong at first — 29,770 characters in a single chunk — but
chunking is by token, and the filler is repetitive enough that it compresses to
443 tokens, comfortably inside one 500-token window. This is deliberate: it is
the only fixture where a chunk covers more than one page.
