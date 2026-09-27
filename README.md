# RAG Chatbot for Class Demo

A Retrieval-Augmented Generation chatbot that answers questions grounded in
uploaded course documents.

| Document | Purpose |
|----------|---------|
| [PRD.md](./PRD.md) | Product requirements, features, success metrics |
| [architecture.md](./architecture.md) | System design, API contract, data models |
| [implementation.md](./implementation.md) | Phase-wise build plan with code |

## Status

Phases 1–5 are complete: backend, document ingestion, chat with streaming, the
React chat interface, and the admin panel. See
[implementation.md](./implementation.md) for remaining phases.

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS + Zustand |
| Backend | Python + FastAPI + SQLAlchemy (async) |
| Vector store | Chroma (persistent, local) |
| LLM | big pickle |
| Embeddings | OpenAI `text-embedding-3-small` |
| Database | SQLite |

## Local Development

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and set OPENAI_API_KEY

uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### Adding an LLM key

`.env` works with no key at all — the backend falls back to an offline
extractive responder, which quotes the retrieved sentences that best match the
question. This project is configured against **Groq**, which serves an
OpenAI-compatible API, so no extra dependency is involved:

```bash
# backend/.env
GROQ_API_KEY=gsk_...
LLM_MODEL=openai/gpt-oss-120b
```

Restart the backend. Check the `mode` field on any chat response — `"groq"`
means the model ran, `"offline-extractive"` means the key was not picked up.

Four things to know before you edit:

- **A key containing `your-key`, or starting with `sk-your`, counts as unset.**
  Deliberate: a freshly copied `.env.example` should not produce auth errors.
- **A real key changes the answers, not the index.** `EMBEDDING_PROVIDER` is
  pinned to `local` in `.env` for exactly this reason. Left on `auto`, adding a
  key would silently change the vector width from 2048 to 1536 and every query
  would then fail with `409 EMBEDDING_MISMATCH` until all documents were
  re-uploaded. Groq does not serve embeddings at all, so it is configured
  independently of the embedding provider and cannot cause this.
- **`LLM_MODEL` must be a name your endpoint serves.** Providers retire models,
  so this drifts: `llama-3.1-8b-instant` was the original choice here and now
  returns 404 on every Groq account. List what your key can reach with
  `curl $GROQ_BASE_URL/models -H "Authorization: Bearer $GROQ_API_KEY"`.
  Currently served and verified: `openai/gpt-oss-120b` (default, best answers,
  ~600ms), `openai/gpt-oss-20b` (cheapest), `qwen/qwen3.8-27b` (fastest,
  ~170ms).
- **`LLM_PROVIDER=groq` is explicit on purpose.** It fails loudly on a bad key
  instead of quietly degrading to the offline responder, which is what you want
  immediately before a demo. Use `auto` for a no-credentials demo. Setting it to
  `openai` is the only way to reach OpenAI while a Groq key is also present.

The trade-off in keeping retrieval local is real but bounded: a hashed bag of
words matches shared wording well and has no synonym knowledge. Measured on the
labelled set, 100% hit@5 for questions reusing the document's own phrasing and
64% for paraphrased ones — see [Testing retrieval](#testing-retrieval). A real
embedding model is the fix for that gap, and it is the one change that requires
re-indexing.

### Inspecting the index

Uploaded files, chunks, and embeddings live under `backend/data/`:

```
backend/data/
├── app.db                    documents, chunks, sessions, messages
├── uploads/                  the raw uploaded files
└── chroma/                   the vectors
```

The embeddings are opaque float arrays, so to actually read them, dump the
index to a text report:

```bash
cd backend

# everything: documents, chunk text, and a summary of each embedding
./venv/bin/python scripts/dump_index.py

# also rank every chunk against a question, showing the scores the
# chat pipeline sees
./venv/bin/python scripts/dump_index.py --query "office hours"

./venv/bin/python scripts/dump_index.py --out -        # print instead of writing
./venv/bin/python scripts/dump_index.py --full         # every dimension
./venv/bin/python scripts/dump_index.py --doc doc_abc123  # one document
```

Writes to `backend/index_dump.txt` by default. On the local embedder the
report decodes each vector back into the terms that produced it, which is what
makes a surprising match explainable:

```
    EMBEDDING:
    dimensions   : 2048
    non-zero     : 157 (7.7% sparse)
    L2 norm     : 1.000000
    top terms by contribution:
      dim   15 = +0.2158  <- week, week_1 +collision
      dim  876 = +0.1878  <- the
      dim  923 = +0.1717  <- course, to_4pm +collision
      dim 1749 = +0.1663  <- percent
      dim  122 = +0.1663  <- and
```

Every contribution is positive. The local embedder accumulates unsigned on
purpose: with signed hashing, two terms colliding in the same dimension with
equal counts and opposite signs cancel *exactly*, which makes a word present in
the document unretrievable by that word. "homework" was annihilated by "trees"
that way, and "What does homework contribute?" returned nothing from the one
document stating the homework weighting. Collisions can now only add to a match,
never erase one — at the cost of unrelated documents sharing some mass, which is
why the offline generator scores individual sentences against the question
before quoting any. See `architecture.md` §4.4.

Chunks can also be read one at a time over HTTP:

```
GET /api/documents/{document_id}/chunks
```

### Testing retrieval

`dump_index.py --query` shows you what one question retrieves. To measure
retrieval rather than eyeball it, use the labelled question set:

```bash
cd backend
./venv/bin/python scripts/eval_retrieval.py --index   # reset + index corpus, then evaluate
./venv/bin/python scripts/eval_retrieval.py           # evaluate the current index
```

It indexes an 8-document, 17-chunk corpus, runs 27 questions through the real
retriever, and reports three numbers: `hit@k` (right document retrieved at
all), `MRR` (how near the top), and `answerable` (was the answer text in the
chunk at rank 1 — the strict one, since the generator only reads the top
chunk).

Measured on the local embedder, `top_k=5`:

| Group | n | hit@5 | MRR | answerable |
|-------|---|-------|-----|------------|
| all | 27 | 85% | 0.74 | 59% |
| verbatim | 16 | **100%** | 0.91 | 75% |
| paraphrased | 11 | **64%** | 0.50 | 36% |

Questions are split by whether they reuse the document's own wording
("When is the midterm examination?") or deliberately avoid it ("How much time
do I get for the last test of the term?"). The gap is the honest result: the
local provider is a hashed bag of words, so it matches shared vocabulary well
and has no synonym knowledge at all. All four document-level misses are
paraphrased questions. That is a property of the embedder, not something
`top_k` can tune away.

The script warns if the index holds no more chunks than `top_k`, because then
every question returns the entire index and `hit@5` is 100% for free — which
is what happens with the two sample documents. See
[`backend/samples/eval/README.md`](backend/samples/eval/README.md).

### Frontend

```bash
cd frontend
npm install
cp .env.example .env    # optional; the dev proxy works without it
npm run dev
```

Runs at http://localhost:5173 and proxies `/api` to the backend, so the browser
stays on one origin and CORS never comes up.

| Command | Does |
|---------|------|
| `npm run dev` | Dev server with HMR |
| `npm run build` | Type-check (`tsc`) then build to `dist/` |
| `npm run preview` | Serve the production build |
| `npm test` | Vitest suite |
| `npm run lint` | ESLint |

### Running both

Two terminals, backend first:

```bash
cd backend && ./venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

Then open http://localhost:5173 and ask a question. If the chat answers
"no documents found", upload something first:

```bash
curl -X POST http://localhost:8000/api/documents/upload -F "file=@syllabus.pdf"
```

## Docker

```bash
docker compose up --build
```

Frontend at http://localhost:3000, backend at http://localhost:8000.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Liveness probe |
| `GET` | `/api/health/ready` | Readiness probe (DB + vector store) |
| `POST` | `/api/documents/upload` | Upload a document |
| `GET` | `/api/documents` | List documents |
| `GET` | `/api/documents/stats` | Index size, embedding model, and the model the index was built with |
| `GET` | `/api/documents/{id}` | One document |
| `GET` | `/api/documents/{id}/chunks` | The chunks a document was split into |
| `DELETE` | `/api/documents/{id}` | Delete a document and its vectors |
| `POST` | `/api/chat/query` | Ask a question |
| `POST` | `/api/chat/stream` | Ask a question (streamed, SSE) |
| `POST` | `/api/chat/clear` | Delete a session and its messages |
| `GET` | `/api/chat/history/{session_id}` | A session's messages, oldest first |

Errors use a single envelope, `{"error": {"code", "message", "details"}}`.

Interactive docs: http://localhost:8000/docs

Note the trailing slash on `/api/documents` — the route is registered as
`/api/documents/`, and the bare path costs a 307 redirect.

## Using the UI

Two routes, switched from the nav bar:

| Route | What it does |
|-------|--------------|
| `/chat` | Ask questions; answers stream in and cite their sources |
| `/admin` | Upload documents, list and delete them, and check system status |

On the admin page:

- **Upload** — drop a PDF/TXT/DOCX/MD onto the box or browse for one. The
  progress bar is followed by a distinct *Indexing document…* phase, because
  the server parses, chunks and embeds the file inside the upload request: the
  bytes finish travelling well before the response comes back.
- **System status** — readiness per dependency, the LLM model, the embedding
  model, and the index size. It also warns when the embedding model is not the
  one the index was built with, which is the state that otherwise turns the
  next upload into a 409.
- **Delete** — asks for confirmation, and keeps the row if the server refuses,
  so a failed delete does not look like a success.

## Tests

```bash
cd backend && ./venv/bin/python -m pytest tests/ -q -p no:logging   # 259
cd frontend && npm test                                            # 177
```

The frontend suite covers the SSE parser against a real capture of the
backend's stream, the error-envelope mapping, the chat store, the admin panel
including the multipart upload headers, and both pages rendered end to end with
a mocked transport.
