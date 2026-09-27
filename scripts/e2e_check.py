#!/usr/bin/env python3
"""End-to-end check against a running backend.

The Phase 6 plan asks for an end-to-end testing checklist. A checklist in a
markdown file gets ticked once and then quietly stops being true, so this is
the same list as code: run it before a demo, and it either prints a clean
board or names the thing that broke.

    python3 scripts/e2e_check.py                    # against localhost:8000
    python3 scripts/e2e_check.py --base-url http://localhost:8000
    python3 scripts/e2e_check.py --with-large       # incl. the 50MB document
    python3 scripts/e2e_check.py --keep             # leave uploads in place

What this cannot check: anything that needs a real browser. The frontend
behaviour in the plan's checklist is covered by the jsdom suite
(frontend/src, 207 tests) and by manual inspection, but not by this script, and
the results below say so rather than implying otherwise.

Exit code is 0 when nothing failed. SKIP never fails the run.
"""

import argparse
import asyncio
import io
import json
import os
import sys
import tempfile
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import httpx
except ImportError:
    sys.exit("httpx is required: pip install -r backend/requirements.txt")

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m",
)
if not sys.stdout.isatty():
    GREEN = RED = YELLOW = DIM = BOLD = RESET = ""

PASS, FAIL, SKIP = "pass", "fail", "skip"

# Mirrors RATE_LIMIT_REQUESTS_PER_MINUTE in backend/.env. This script's own
# requests count against the same per-minute budget as any client, which is why
# the concurrency check can end up measuring the limiter instead of the
# server. Override to match a non-default deployment.
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))


class _Skip(Exception):
    """Raised by a check that cannot be answered on this run.

    Distinct from a failure: a check that says "I could not measure this" is
    more useful than one that guesses, and reporting it as a pass would be a
    claim the numbers do not support.
    """

# Small enough to be a fast, obviously-valid document; the content is what the
# grounded-answer checks look for.
SAMPLE = """CS 401 Machine Learning -- Meeting Notes

The final examination accounts for 40 percent of the course grade.
Weekly problem sets account for 30 percent and participation for 10 percent.
Office hours are held on Tuesdays from 2pm to 4pm in Gates 412.
The teaching assistant is Priya Raman, reachable at priya@example.edu.
"""


class Results:
    def __init__(self) -> None:
        self.rows: List[Tuple[str, str, str, str]] = []

    def add(self, section: str, name: str, status: str, note: str = "") -> None:
        self.rows.append((section, name, status, note))

    @property
    def failures(self) -> int:
        return sum(1 for r in self.rows if r[2] == FAIL)

    @property
    def skips(self) -> int:
        return sum(1 for r in self.rows if r[2] == SKIP)

    def report(self) -> None:
        section = None
        for sec, name, status, note in self.rows:
            if sec != section:
                section = sec
                print("\n%s%s%s" % (BOLD, sec, RESET))
            colour = {PASS: GREEN, FAIL: RED, SKIP: YELLOW}[status]
            label = {PASS: "PASS", FAIL: "FAIL", SKIP: "SKIP"}[status]
            line = "  %s%-4s%s %s" % (colour, label, RESET, name)
            if note:
                line += "\n       %s%s%s" % (DIM, note, RESET)
            print(line)

        total = len(self.rows)
        print("\n" + "-" * 62)
        summary = "%d checks, %s%d failed%s, %d skipped" % (
            total,
            RED if self.failures else GREEN,
            self.failures,
            RESET,
            self.skips,
        )
        print(summary if not self.failures else summary)
        if not self.failures:
            print(GREEN + "Backend is ready to demo." + RESET)


class Check:
    """Records a result, turning an unexpected exception into a failure.

    A check that raises must not abort the run: the point is to get through the
    whole list so a single broken thing does not hide the next nine.
    """

    def __init__(self, results: Results, section: str) -> None:
        self.results = results
        self.section = section

    def run(self, name: str, fn: Callable[[], Tuple[bool, str]]) -> None:
        try:
            ok, note = fn()
            self.results.add(self.section, name, PASS if ok else FAIL, note)
        except _Skip as exc:
            self.results.add(self.section, name, SKIP, str(exc))
        except Exception as exc:  # noqa: BLE001 - deliberately broad
            detail = "%s: %s" % (type(exc).__name__, str(exc)[:160])
            self.results.add(self.section, name, FAIL, detail)


def timings(results: Results, section: str) -> None:
    """Print the measured latencies against the plan's targets."""
    rows = [r for r in results.rows if r[0] == section]
    if not rows:
        return
    print("\n%s%s%s" % (BOLD, section, RESET))
    for _, name, _, note in rows:
        print("  %s%s%s  %s" % (DIM, note, RESET, name))


def make_file(filename: str, content: bytes) -> Tuple[str, io.BytesIO]:
    return filename, io.BytesIO(content)


def upload(client: httpx.Client, filename: str, content: bytes,
           ctype: str = "text/plain") -> httpx.Response:
    # `/upload`, not `/documents`: the collection route is GET-only, and
    # POSTing to it gets a 307 that a careless client follows into a GET.
    return client.post(
        "/api/documents/upload",
        files={"file": (filename, content, ctype)},
        timeout=300.0,
    )


def wait_processed(client: httpx.Client, doc_id: str, timeout: float = 120.0) -> Dict[str, Any]:
    """Poll until the document leaves the pending/processing states."""
    deadline = time.time() + timeout
    last: Dict[str, Any] = {}
    while time.time() < deadline:
        items = client.get("/api/documents/").json().get("documents", [])
        for doc in items:
            if doc["id"] == doc_id:
                last = doc
                if doc["status"] in ("processed", "failed"):
                    return doc
        time.sleep(0.25)
    return last


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default=os.environ.get("E2E_BASE_URL",
                                                         "http://localhost:8000"))
    ap.add_argument("--with-large", action="store_true",
                    help="also process a valid 50MB document (slow)")
    ap.add_argument("--keep", action="store_true", help="do not delete uploaded documents")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    tag = uuid.uuid4().hex[:8]
    created: List[str] = []
    results = Results()

    client = httpx.Client(base_url=base, timeout=60.0)
    try:
        # -- reachability ---------------------------------------------------
        reach = Check(results, "Backend")

        def reachable() -> Tuple[bool, str]:
            r = client.get("/api/health")
            if r.status_code != 200:
                return False, "GET /api/health -> %d" % r.status_code
            body = r.json()
            return True, "model=%s env=%s" % (body.get("llm_model"), body.get("environment"))

        reach.run("Backend is up", reachable)

        # -- uploads --------------------------------------------------------
        up = Check(results, "Uploads")

        def do_upload(name: str, content: bytes, ctype: str,
                      want: int) -> Optional[httpx.Response]:
            r = upload(client, name, content, ctype)
            if r.status_code != want:
                return None
            if want == 201:
                doc_id = r.json().get("id")
                if doc_id:
                    created.append(doc_id)
            return r

        def upload_txt() -> Tuple[bool, str]:
            name = "e2e-notes-%s.txt" % tag
            started = time.time()
            r = upload(client, name, SAMPLE.encode())
            if r.status_code != 201:
                return False, "TXT upload -> %d (expected 201): %s" % (
                    r.status_code, r.text[:120])
            doc_id = r.json()["id"]
            created.append(doc_id)
            doc = wait_processed(client, doc_id)
            elapsed = time.time() - started
            if doc.get("status") != "processed":
                return False, "status=%s %s" % (doc.get("status"), doc.get("error"))
            return True, "%d chunks in %.0fms" % (doc.get("chunk_count", 0), elapsed * 1000)

        up.run("TXT upload accepted and indexed", upload_txt)

        def upload_pdf() -> Tuple[bool, str]:
            # A real, minimal one-page PDF. Hand-built rather than skipped so
            # the PDF path (pypdf) is genuinely exercised.
            pdf = build_minimal_pdf()
            name = "e2e-sheet-%s.pdf" % tag
            r = upload(client, name, pdf, "application/pdf")
            if r.status_code != 201:
                return False, "PDF upload -> %d: %s" % (r.status_code, r.text[:120])
            doc_id = r.json()["id"]
            created.append(doc_id)
            doc = wait_processed(client, doc_id)
            if doc.get("status") != "processed":
                return False, "status=%s" % doc.get("status")
            return True, "pypdf extracted %d chunk(s)" % doc.get("chunk_count", 0)

        up.run("PDF upload accepted and indexed", upload_pdf)

        def upload_docx() -> Tuple[bool, str]:
            name = "e2e-doc-%s.docx" % tag
            r = upload(client, name, build_minimal_docx(),
                       "application/vnd.openxmlformats-officedocument."
                       "wordprocessingml.document")
            if r.status_code != 201:
                return False, "DOCX upload -> %d: %s" % (r.status_code, r.text[:120])
            doc_id = r.json()["id"]
            created.append(doc_id)
            doc = wait_processed(client, doc_id)
            if doc.get("status") != "processed":
                return False, "status=%s" % doc.get("status")
            return True, "python-docx path ok"

        up.run("DOCX upload accepted and indexed", upload_docx)

        def reject_bad_type() -> Tuple[bool, str]:
            r = upload(client, "e2e-bad-%s.exe" % tag, b"MZ\x90\x00", "application/octet-stream")
            if r.status_code != 400:
                return False, "expected 400, got %d: %s" % (r.status_code, r.text[:120])
            code = r.json().get("error", {}).get("code")
            return True, "rejected as %s" % code

        up.run("Unsupported file type rejected", reject_bad_type)

        def reject_oversize() -> Tuple[bool, str]:
            # Just over the 50MB limit, so the test is on the limit's behaviour
            # and not on an unrelated size error.
            blob = b"x" * (55 * 1024 * 1024)
            r = upload(client, "e2e-huge-%s.txt" % tag, blob)
            if r.status_code != 400:
                return False, "expected 400 for 55MB, got %d" % r.status_code
            return True, "55MB rejected as %s" % r.json().get("error", {}).get("code")

        up.run("File over 50MB rejected", reject_oversize)

        def appears_in_list() -> Tuple[bool, str]:
            docs = client.get("/api/documents/").json().get("documents", [])
            names = {d["filename"] for d in docs}
            expected = ["e2e-notes-%s.txt" % tag, "e2e-sheet-%s.pdf" % tag]
            missing = [n for n in expected if n not in names]
            if missing:
                return False, "missing from list: %s" % missing
            return True, "%d document(s) listed" % len(docs)

        up.run("Uploaded documents appear in the list", appears_in_list)

        # -- retrieval and answering ---------------------------------------
        chat = Check(results, "Chat")

        def ask(question: str) -> httpx.Response:
            return client.post("/api/chat/query",
                               json={"question": question, "session_id": "e2e-%s" % tag},
                               timeout=120.0)

        def grounded_answer() -> Tuple[bool, str]:
            started = time.time()
            r = ask("Who is the teaching assistant?")
            elapsed = time.time() - started
            if r.status_code != 200:
                return False, "-> %d: %s" % (r.status_code, r.text[:160])
            body = r.json()
            answer = body.get("answer", "")
            if "Priya Raman" not in answer:
                return False, "answer did not contain the expected name: %r" % answer[:120]
            if not body.get("sources"):
                return False, "answer carried no sources"
            return True, "mode=%s %.0fms, %d source(s)" % (
                body.get("mode"), elapsed * 1000, len(body["sources"]))

        chat.run("Question answered from the document, with sources", grounded_answer)

        def cites_filename() -> Tuple[bool, str]:
            body = ask("When are office hours?").json()
            files = {s["filename"] for s in body.get("sources", [])}
            hit = [f for f in files if f.startswith("e2e-notes")]
            if not hit:
                return False, "sources did not include the uploaded file: %s" % files
            return True, "cited %s" % sorted(hit)

        chat.run("Citation points at the uploaded file", cites_filename)

        def declines_unknown() -> Tuple[bool, str]:
            r = ask("What is the registration number of the quantum reactor?")
            if r.status_code != 200:
                return False, "-> %d" % r.status_code
            answer = r.json().get("answer", "").lower()
            # The property that matters: no fabricated specifics.
            fabricated = any(w in answer for w in ("#4471", "4471-a", "registration number is"))
            if fabricated:
                return False, "invented a specific value: %r" % answer[:140]
            declined = any(w in answer for w in
                           ("don't have", "do not have", "no information", "not in the",
                            "cannot find", "couldn't find"))
            if not declined:
                return False, "did not decline, and did not fabricate: %r" % answer[:140]
            return True, "declined rather than inventing a value"

        chat.run("Out-of-scope question declined, not invented", declines_unknown)

        def reports_mode() -> Tuple[bool, str]:
            r = ask("Who is the TA?")
            if r.status_code != 200:
                return False, "-> %d" % r.status_code
            mode = r.json().get("mode")
            if not mode:
                return False, "no mode field on the response"
            honest = mode in ("groq", "openai", "offline-extractive")
            return (True, "mode=%s" % mode) if honest else (False, "unexpected mode %r" % mode)

        chat.run("Response names the generator that ran", reports_mode)

        def session_history() -> Tuple[bool, str]:
            sid = "e2e-hist-%s" % tag
        # `POST /api/chat/clear`, not `DELETE /api/chat/history/{id}`: the
        # history route is GET-only, and DELETE against it is a 405 that looks
        # like a broken clear button if you only ever test it by hand once.
            client.post("/api/chat/query",
                        json={"question": "Who is the TA?", "session_id": sid}, timeout=60.0)
            hist = client.get("/api/chat/history/%s" % sid)
            if hist.status_code != 200:
                return False, "GET history -> %d" % hist.status_code
            msgs = hist.json().get("messages", [])
            if len(msgs) < 2:
                return False, "expected a question and an answer, got %d" % len(msgs)
            return True, "%d message(s) persisted under the client's own id" % len(msgs)

        chat.run("Session history persists across requests", session_history)

        def clear_session() -> Tuple[bool, str]:
            sid = "e2e-clear-%s" % tag
            client.post("/api/chat/query",
                        json={"question": "Who is the TA?", "session_id": sid}, timeout=60.0)
            r = client.post("/api/chat/clear", json={"session_id": sid})
            if r.status_code != 200:
                return False, "POST /api/chat/clear -> %d: %s" % (r.status_code, r.text[:120])
            if r.json().get("messages_removed", 0) < 2:
                return False, "clear reported %s removed" % r.json().get("messages_removed")
            after = client.get("/api/chat/history/%s" % sid).json().get("messages", [])
            if after:
                return False, "%d message(s) survived the clear" % len(after)
            return True, "history emptied"

        chat.run("Clearing a session removes its history", clear_session)

        # -- streaming ------------------------------------------------------
        st = Check(results, "Streaming")

        def stream_start() -> Tuple[bool, str]:
            started = time.time()
            first = None
            frames = 0
            with client.stream(
                "POST", "/api/chat/stream",
                json={"question": "Who is the teaching assistant?", "session_id": "e2e-s-%s" % tag},
                headers={"Accept": "text/event-stream"}, timeout=120.0,
            ) as resp:
                if resp.status_code != 200:
                    return False, "-> %d" % resp.status_code
                ctype = resp.headers.get("content-type", "")
                if "text/event-stream" not in ctype:
                    return False, "content-type=%r" % ctype
                text = []
                for line in resp.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    if first is None:
                        first = time.time() - started
                    frames += 1
                    payload = json.loads(line[5:])
                    if payload.get("finish"):
                        break
                    text.append(payload.get("delta", ""))
            if first is None:
                return False, "no data frames arrived"
            if frames < 2:
                return False, "only %d frame(s): response was not incremental" % frames
            answer = "".join(text).strip()
            if "Priya Raman" not in answer:
                return False, "streamed text missing the answer: %r" % answer[:100]
            return True, "first frame in %.0fms, %d frames, answer complete" % (
                first * 1000, frames)

        st.run("Stream delivers deltas incrementally", stream_start)

        def stream_terminal_frame() -> Tuple[bool, str]:
            last: Dict[str, Any] = {}
            with client.stream(
                "POST", "/api/chat/stream",
                json={"question": "When are office hours?", "session_id": "e2e-t-%s" % tag},
                timeout=120.0,
            ) as resp:
                for line in resp.iter_lines():
                    if line.startswith("data:"):
                        payload = json.loads(line[5:])
                        if payload.get("finish"):
                            last = payload
            missing = [k for k in ("mode", "sources") if k not in last]
            if missing:
                return False, "terminal frame missing %s" % missing
            if not last["sources"]:
                return False, "terminal frame carried no sources"
            return True, "mode=%s, %d source(s) on the final frame" % (
                last["mode"], len(last["sources"]))

        st.run("Terminal frame carries mode and sources", stream_terminal_frame)

        # -- error handling -------------------------------------------------
        err = Check(results, "Error handling")

        def envelope_on_404() -> Tuple[bool, str]:
            r = client.get("/api/documents/doc_does_not_exist")
            if r.status_code != 404:
                return False, "-> %d" % r.status_code
            body = r.json()
            shape = isinstance(body, dict) and set(body.get("error", {})) >= {"code", "message"}
            if not shape:
                return False, "not an error envelope: %s" % r.text[:140]
            return True, "code=%s" % body["error"]["code"]

        err.run("Unknown document returns a structured error", envelope_on_404)

        def empty_question() -> Tuple[bool, str]:
            r = client.post("/api/chat/query", json={"question": "", "session_id": "x"})
            if r.status_code != 422:
                return False, "expected 422, got %d" % r.status_code
            return True, "validation error, not a crash"

        err.run("Empty question rejected as invalid", empty_question)

        def too_long_question() -> Tuple[bool, str]:
            r = client.post("/api/chat/query", json={"question": "a" * 6000})
            if r.status_code != 422:
                return False, "expected 422 for an over-long question, got %d" % r.status_code
            return True, "length limit enforced"

        err.run("Over-long question rejected", too_long_question)

        # -- performance ----------------------------------------------------
        perf = Check(results, "Performance")

        def upload_speed() -> Tuple[bool, str]:
            name = "e2e-perf-%s.txt" % tag
            body = (SAMPLE * 40).encode()
            started = time.time()
            r = upload(client, name, body)
            if r.status_code != 201:
                return False, "-> %d" % r.status_code
            doc_id = r.json()["id"]
            created.append(doc_id)
            wait_processed(client, doc_id)
            elapsed = time.time() - started
            ok = elapsed < 3.0
            return ok, "%.0fKB in %.2fs (target < 3s)%s" % (
                len(body) / 1024, elapsed, "" if ok else " -- OVER BUDGET")

        perf.run("Upload and index a ~14KB document", upload_speed)

        def query_speed() -> Tuple[bool, str]:
            worst = 0.0
            for q in ("Who is the TA?", "When is the project proposal due?",
                      "What counts towards the final grade?"):
                started = time.time()
                r = ask(q)
                if r.status_code != 200:
                    return False, "'%s' -> %d" % (q, r.status_code)
                worst = max(worst, time.time() - started)
            ok = worst < 5.0
            return ok, "slowest of 3 questions %.2fs (target < 5s)%s" % (
                worst, "" if ok else " -- OVER BUDGET")

        perf.run("Query response time", query_speed)

        def concurrency() -> Tuple[bool, str]:
            async def run() -> Tuple[List[Tuple[int, str]], float]:
                async with httpx.AsyncClient(base_url=base, timeout=120.0) as ac:
                    started = time.time()
                    responses = await asyncio.gather(*[
                        ac.post("/api/chat/query",
                                json={"question": "Who is the TA?",
                                      "session_id": "e2e-c-%s-%d" % (tag, i)})
                        for i in range(10)
                    ], return_exceptions=True)
                    out = []
                    for r in responses:
                        if isinstance(r, Exception):
                            out.append((0, type(r).__name__))
                        else:
                            code = ""
                            if r.status_code != 200:
                                try:
                                    code = r.json().get("error", {}).get("code", "")
                                except Exception:
                                    code = ""
                            out.append((r.status_code, code))
                    return out, time.time() - started

            outcomes, elapsed = asyncio.run(run())
            ok = sum(1 for c, _ in outcomes if c == 200)
            throttled = sum(1 for c, _ in outcomes if c == 429)
            upstream = sum(1 for c, code in outcomes if c == 503 and code == "LLM_UNAVAILABLE")
            note = "%d/10 in %.2fs (%d 429, %d upstream-throttled)" % (
                ok, elapsed, throttled, upstream)

            if ok == 10:
                return True, note
            if ok + upstream == 10:
                # The provider's quota, not this server. The free Groq tier
                # allows 8000 tokens/minute, and ten answers cost more than
                # that between them, so the upstream call is throttled and the
                # backend reports it as LLM_UNAVAILABLE. It did the right
                # thing -- retried, then failed loudly instead of hanging or
                # inventing an answer -- so the server passes; what could not be
                # measured is concurrency under the quota.
                raise _Skip(
                    "%s. Measured the provider's per-minute token quota, not "
                    "server concurrency: the free tier allows 8000 tokens/min, "
                    "which ten answers exceed. Raise the quota (or ask fewer "
                    "questions at once) to test this." % note
                )
            if ok + throttled == 10:
                raise _Skip(
                    "%s -- this script's own requests had already spent the "
                    "%d-req/min budget, so this measures the limiter rather "
                    "than concurrency." % (note, RATE_LIMIT_PER_MINUTE)
                )
            other = sorted({c for c, _ in outcomes if c not in (200, 429, 503)})
            return False, "%s, unexpected statuses %s" % (note, other or "none")

        # `Check.run` turns a _Skip into a SKIP row, so an unmeasurable check
        # neither fails the run nor gets silently reported as a pass.
        perf.run("10 concurrent queries", concurrency)

        def rate_limit_works() -> Tuple[bool, str]:
            """The limiter is a feature; confirm it engages and answers cleanly.

            A rate limit that returns a 500, or a 429 with no body, turns a
            throttle into an unexplained failure in front of an audience.
            """
            codes = []
            for _ in range(RATE_LIMIT_PER_MINUTE + 20):
                r = client.get("/api/health")
                codes.append(r.status_code)
                if r.status_code == 429:
                    break
            if 429 not in codes:
                return False, "never rate limited after %d requests" % len(codes)
            r = client.get("/api/health")
            try:
                shaped = "error" in r.json()
            except Exception:
                shaped = False
            return True, "429 after %d request(s)%s" % (
                codes.index(429) + 1,
                ", structured error body" if shaped else ", empty body",
            )

        def large_document() -> Tuple[bool, str]:
            name = "e2e-large-%s.txt" % tag
            body = (SAMPLE * 40000).encode()  # ~18MB of real, valid text
            started = time.time()
            r = upload(client, name, body)
            if r.status_code != 201:
                return False, "-> %d" % r.status_code
            doc_id = r.json()["id"]
            created.append(doc_id)
            doc = wait_processed(client, doc_id, timeout=900.0)
            elapsed = time.time() - started
            if doc.get("status") != "processed":
                return False, "status=%s after %.0fs" % (doc.get("status"), elapsed)
            return True, "%.0fMB in %.0fs, %d chunks" % (
                len(body) / 1024 / 1024, elapsed, doc.get("chunk_count", 0))

        if args.with_large:
            perf.run("Large document (~18MB) processes", large_document)
        else:
            results.add("Performance", "Large document processes",
                        SKIP, "pass --with-large to include it; it takes minutes")

        # -- frontend (not exercised here) ----------------------------------
        for item in ("Landing page renders", "Navigation between routes",
                     "Upload progress displays", "Streaming response displays",
                     "Source citations appear", "Clear chat works",
                     "Suggested questions work", "Error messages display"):
            results.add("Frontend", item, SKIP,
                        "needs a browser; covered by the jsdom suite in frontend/src")

        results.add("Frontend", "Rendering verified in a real browser", SKIP,
                    "no browser was attached when this ran -- jsdom is not a browser")

        # -- cleanup --------------------------------------------------------
        if created and not args.keep:
            removed = 0
            for doc_id in list(created):
                r = client.delete("/api/documents/%s" % doc_id)
                if r.status_code in (200, 204, 404):
                    removed += 1
            results.add("Cleanup", "Test documents removed", PASS,
                        "%d deleted" % removed if not args.keep
                        else "left in place (--keep)")

        def delete_removes() -> Tuple[bool, str]:
            r = upload(client, "e2e-del-%s.txt" % tag, SAMPLE.encode())
            if r.status_code != 201:
                return False, "upload -> %d" % r.status_code
            doc_id = r.json()["id"]
            d = client.delete("/api/documents/%s" % doc_id)
            if d.status_code not in (200, 204):
                return False, "delete -> %d" % d.status_code
            names = {x["filename"] for x in
                     client.get("/api/documents/").json().get("documents", [])}
            if "e2e-del-%s.txt" % tag in names:
                return False, "still present after delete"
            return True, "gone from the list"

        delete_check = Check(results, "Cleanup")
        delete_check.run("Delete removes a document", delete_removes)

        # Genuinely last: this one exhausts the per-minute budget on purpose, so
        # anything after it would be measuring a throttled backend.
        perf.run("Rate limit engages with a clean response", rate_limit_works)

    except httpx.HTTPError as exc:
        print(RED + "Could not reach %s: %s" % (base, exc) + RESET)
        print("Is the backend running?  cd backend && "
              "./venv/bin/uvicorn app.main:app --port 8000")
        return 2
    finally:
        client.close()

    results.report()
    timings(results, "Performance")
    print()
    return 1 if results.failures else 0


def build_minimal_pdf() -> bytes:
    """A valid single-page PDF with real extractable text.

    Hand-assembled because a checked-in binary fixture cannot be reviewed in a
    diff, and because the point is to exercise pypdf's text extraction rather
    than to test a particular PDF.
    """
    import zlib

    text = "CS 401 revision sheet. The midterms account for 20 percent."
    stream = ("BT /F1 12 Tf 40 700 Td (%s) Tj ET" % text).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref_at = out.tell()
    out.write(b"xref\n0 %d\n" % (len(objects) + 1))
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
              % (len(objects) + 1, xref_at))
    return out.getvalue()


def build_minimal_docx() -> bytes:
    """A valid .docx (a zip with the three parts python-docx requires)."""
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                   "</Types>")
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                   "</Relationships>")
        z.writestr("word/document.xml",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                   "<w:body><w:p><w:r><w:t>CS 401 lab schedule. Labs are due "
                   "Thursdays at 11:59pm in the submission box.</w:t></w:r></w:p>"
                   "</w:body></w:document>")
    return buf.getvalue()


if __name__ == "__main__":
    sys.exit(main())
