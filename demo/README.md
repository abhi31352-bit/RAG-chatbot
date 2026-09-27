# Demo runbook

Everything needed to run this in front of a class, in the order you need it.

- **Before you start:** the [pre-flight](#pre-flight) list. Ten minutes, and it
  catches every problem that has actually gone wrong.
- **The run itself:** a [timed runbook](#the-run) with what to say and what to
  click.
- **When it breaks:** [failure modes](#if-something-breaks) and what to do about
  each one.

---

## The one thing to know first

Answers come from Groq's free tier, which allows **8,000 tokens per minute**.
One answer costs roughly 1,400–1,800 tokens once the retrieved passages and the
prompt are counted, so the budget is about **five questions a minute**.

Ask them faster than that and the provider returns a 429, the backend reports
`LLM_UNAVAILABLE`, and the UI shows an error after roughly 20 seconds of
apparent hanging — the SDK retries twice before giving up. This is the single
most likely way the demo goes wrong, and it is entirely avoidable by **pausing
two or three seconds between questions and narrating while the answer streams in**.

A narrated demo is slower than a silent one anyway, so the constraint mostly
takes care of itself. If you have to recover from it, the wait is under a
minute.

To confirm your current allowance without spending one:

```bash
curl -s localhost:8000/api/health
```

---

## Pre-flight

Ten minutes before you present.

### 1. Start the stack, with a clean index

```bash
# Dev
cd backend && ./venv/bin/uvicorn app.main:app --port 8000     # terminal 1
cd frontend && npm run dev                                     # terminal 2
# -> http://localhost:5173

# Or Docker, which serves the built app on :3000
docker compose up --build
```

### 2. Wipe and re-upload the sample documents

Do this every time. A previous session's leftover documents dilute every answer,
and it is the most common cause of "the bot gave me the wrong thing".

```bash
# Delete everything currently indexed
curl -s localhost:8000/api/documents/ \
  | python3 -c "import sys,json; [print(d['id']) for d in json.load(sys.stdin)['documents']]" \
  | xargs -I{} curl -s -X DELETE localhost:8000/api/documents/{}

# Upload the three sample documents
for f in demo/sample-documents/*; do
  curl -s -X POST localhost:8000/api/documents/upload -F "file=@$f" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['filename'], d['status'], d['chunk_count'])"
done
```

Expect three lines, all `processed`: `syllabus.txt` (1 chunk),
`lecture-notes-week1.md` (3), `course-schedule.md` (1).

### 3. Run the automated check

```bash
./backend/venv/bin/python scripts/e2e_check.py
```

This exercises uploads, chat, streaming, error handling and the latency targets
against the running server, and cleans up after itself. **A clean board means the
backend is ready.** It also deliberately trips the rate limit as its last step,
so wait a moment before starting the demo — or run it and then wait for the
one-minute window to reset.

### 4. Check the model is actually reachable

```bash
curl -s localhost:8000/api/health
```

Look for `"llm_model": "openai/gpt-oss-120b"`. If instead you see
`offline-extractive` in the answer badge during the demo, the key is not being
read — see [failure modes](#if-something-breaks).

### 5. Open the browser tabs you want

- `http://localhost:5173` (or `:3000` for Docker) — the landing page
- The same URL with `/admin` open in a second tab, so you can switch without a
  page load if you need to re-upload

Turn on the browser's network throttling **off**. A hard refresh on `/chat` or
`/admin` only works because the dev server and the nginx config both fall back to
`index.html`; that has been configured, but a cached error page is not worth
discovering live.

---

## The run

About six minutes. Timings are generous — if you are ahead, ask a question from
the [verified list](#verified-questions) and let the answer stream.

### 0:00 — The premise (30s)

Open the landing page. Say what the thing is:

> This is a retrieval-augmented chatbot. It answers questions using documents
> that have been uploaded to it, and it shows you which passage each answer
> came from. The interesting part isn't that it answers questions — it's that
> it can only answer from the material, and it tells you when your question
> falls outside it.

### 0:30 — The pipeline (45s)

Click **How it works**. Walk the four steps: upload, index, ask, answer. Do not
read the text out. One sentence each.

### 1:15 — Upload (60s)

Switch to **Documents**. Show the three indexed files and the chunk counts.

> Three documents, five chunks total. The chunking is what makes the citation
> possible — an answer points at a specific passage, not a whole file.

Then upload something new to show it live. Use a file that is not already
indexed — anything in TXT, MD, PDF or DOCX under 50MB. The upload is a couple of
seconds; narrate over it.

> It parses the file, splits it into overlapping passages, and embeds each one.

### 2:15 — Grounded answer (90s)

Switch to **Chat**. Click the first suggested question — *"What counts towards
the final grade?"* — and **let it stream**. The typing animation is the point;
do not click again while it is running.

> The answer is 40% for the final exam. The source is underneath, and it points
> at the passage in the syllabus that says so. That's a quote, not a
> recollection — I can open the file and check it.

### 2:45 — Retrieval actually discriminates (60s)

This is the best 60 seconds in the demo, because it shows the retrieval is real.
Ask two questions that belong to *different* documents and point out that the
citation changes:

| Ask | Watch for |
|-----|-----------|
| *"Explain how gradient descent chooses its step size."* | cites `lecture-notes-week1.md` |
| *"When is midterm 2 held?"* | cites `course-schedule.md` |

> Same question type, completely different passages, and the citation follows.
> It's not pattern-matching the syllabus text — the vector search is picking
> between documents.

### 3:45 — It declines (45s)

The credibility beat. Ask something the material genuinely does not cover:

> *"What's the capital of France?"*

> It says it doesn't have that. That's the behaviour I'd want — if it
> hallucinated a confident answer here, you would have no way to tell from the
> grounded ones.

### 4:30 — Sources and honesty (45s)

Scroll to the source cards. Mention the mode badge, which says which generator
produced the answer.

> That's the real model being called, live. [If time: it also runs with no API
> key at all, in a purely extractive mode that quotes sentences — and the badge
> says so, rather than pretending.]

### 5:15 — Questions (rest of the time)

Run down the [verified questions](#verified-questions). If someone asks
something cleverer than you prepared for, prefer a question from the
course material — it is the case you can answer.

---

## Verified questions

Every one of these was run against this build and checked for **two** things:
that the answer is right, and that it cites the document it should.

| Question | Should cite | Should mention |
|----------|--------------|----------------|
| What counts towards the final grade? | `syllabus.txt` | 40% final exam, 30% problem sets |
| What happens if I submit an assignment late? | `syllabus.txt` | 10% per day, 50% cap |
| Who should I contact first about an academic question? | `syllabus.txt` | the instructor, then the TA |
| Who is the TA? | `syllabus.txt` | Priya Raman |
| When are the office hours? | `syllabus.txt` | Tuesdays 2–4pm, Gates 412 |
| Explain how gradient descent chooses its step size. | `lecture-notes-week1.md` | learning rate |
| What are the three parts of the mean squared error decomposition? | `lecture-notes-week1.md` | bias, variance, irreducible noise |
| What is dataset shift? | `lecture-notes-week1.md` | train/test drawn from different distributions |
| When is midterm 2 held? | `course-schedule.md` | week 5, fifth Tuesday |
| How many office hours run in week 10? | `course-schedule.md` | 2 hours |

### Questions that deliberately get declined

Use these to demonstrate the honesty behaviour. All three return *"I don't have
information about that in the course materials."*

- What is the capital of France?
- Who won the 2018 World Cup?
- What is quantum chromodynamics?

---

## If something breaks

### The answer takes ~20 seconds and then shows an error

**The provider's per-minute token limit.** Retries have already happened by the
time the error appears. Wait 30–60 seconds, then ask the question again. Say
something if you are mid-demo — "that's the free tier's rate limit, it resets
every minute" reads as competence, not failure.

If you have a paid key, setting `GROQ_API_KEY` to it removes this entirely.

### The badge says `offline-extractive` instead of the model name

The key is not being read. `backend/.env` is only loaded when uvicorn is started
**from the `backend/` directory**:

```bash
cd backend && ./venv/bin/uvicorn app.main:app --port 8000
```

The app still works in offline mode — it quotes sentences out of the material
instead of writing a new answer. It is a worse demo, and questions phrased with
vocabulary the documents never use will fall back even though the right passage
was retrieved. That is a limitation of the offline responder's literal term
matching, not of retrieval.

### The bot answers from memory, with no sources

Nothing is indexed. Check the admin page, and confirm the documents finished
processing rather than still being pending.

### An upload fails with 413

nginx caps request bodies at 60 MB, the app at 50. A file above 50 MB is
rejected by design. The 413 you would see is the proxy, so the message names
nginx rather than the app — the file is simply too large.

### The page is blank after a refresh

`try_files $uri $uri/ /index.html` handles this and is configured in both the
dev server and `frontend/nginx.conf`. If it happens, you are probably on a build
served without that fallback. Reload from `/` and navigate in.

### The model name returns `model_not_found`

Provider model catalogues change. List what is actually available:

```bash
set -a && source backend/.env && set +a
curl -s "$GROQ_BASE_URL/models" -H "Authorization: Bearer $GROQ_API_KEY" \
  | python3 -c "import sys,json; [print(m['id']) for m in json.load(sys.stdin)['data']]"
```

Then set `LLM_MODEL` in `backend/.env` to one of those and restart. `big-pickle`
and `llama-3.1-8b-instant` have both been retired; `openai/gpt-oss-120b` was
working when this was written.

### Everything is on fire

The demo runs with no keys at all:

```bash
# Stop the servers, clear the key from backend/.env, restart
```

Offline extractive mode answers from the indexed material by quoting sentences.
It is noticeably more mechanical than the model path, and a few well-phrased
questions will fall back — but it never invents anything, so the citation and
declining behaviour still come through.

---

## What has and has not been verified

Stated plainly, because it affects how much to trust this on the day.

**Verified by running it:**

- All ten questions in the table above, live, for both answer content and
  correct source attribution
- The three declining questions
- Upload, indexing, listing and deletion for TXT, PDF and DOCX
- Streaming, including incremental deltas and the terminal frame carrying mode
  and sources
- Latency: upload ~50ms, query 0.9–1.5s, first streamed frame ~600–900ms
- Rejection of unsupported types and of files over the size limit
- The rate limiter, which returns a structured 429

**Verified by automated tests, not by a human looking at it:**

- The frontend. 207 tests run in jsdom, which is not a browser. Routing,
  rendering, the streaming UI and the admin panel are covered by tests, and the
  production build compiles clean, but **no one has watched this render in a real
  browser.** If the layout looks wrong, that is the explanation.

**Not verified:**

- `docker compose up`. Docker was not installed on the machine this was built
  on. The compose file and both Dockerfiles are written and the configuration is
  checked — every environment variable validated against the settings model,
  every path made absolute and consistent, the nginx config checked for balance
  and for the directives streaming and uploads depend on — but no image has ever
  been built. **Do not plan to demo from Docker until you have run
  `docker compose up --build` yourself, with time to fix what breaks.**
- The 3.11 Python runtime in the container, versus the 3.9 used everywhere else.
