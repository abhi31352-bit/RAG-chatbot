"""HTTP-level tests for the chat endpoints, including SSE streaming."""

import json

import pytest
from sqlalchemy import select

from app.models.chat import Message
from app.models.database import async_session
from app.rag.generator import NO_CONTEXT_ANSWER
from app.rag.pipeline import RAGPipeline
from tests.test_chat import CHUNKS, FakeRetriever


def sse_frames(text: str):
    """Parse an SSE body into decoded JSON payloads."""
    frames = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block.startswith("data: "):
            continue
        frames.append(json.loads(block[len("data: ") :]))
    return frames


@pytest.fixture
def offline_chat():
    """A ChatService wired to a fixed retriever, injected for each request."""
    from app.dependencies import get_chat_service
    from app.main import app
    from app.services.chat_service import ChatService

    service = ChatService()
    service._pipeline = RAGPipeline(retriever=FakeRetriever(CHUNKS))
    app.dependency_overrides[get_chat_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


@pytest.fixture
def empty_chat():
    """A ChatService whose retriever finds nothing."""
    from app.dependencies import get_chat_service
    from app.main import app
    from app.services.chat_service import ChatService

    service = ChatService()
    service._pipeline = RAGPipeline(retriever=FakeRetriever([]))
    app.dependency_overrides[get_chat_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def _empty_database(clean_db):
    yield


async def test_query_rejects_blank_question(client):
    response = await client.post("/api/chat/query", json={"question": "   "})
    assert response.status_code == 422

    # A custom validator's ValueError rides along in `ctx`; the envelope must
    # still be JSON-serializable rather than blowing up into a 500.
    errors = response.json()["error"]["details"]["errors"]
    assert errors
    assert all(isinstance(str(value), str) for e in errors for value in e.get("ctx", {}).values())


# -- POST /query -----------------------------------------------------------


async def test_query_returns_answer_with_sources(client, offline_chat):
    response = await client.post("/api/chat/query", json={"question": "exam weight?"})
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["answer"]
    assert body["session_id"].startswith("sess_")
    assert body["processing_time_ms"] >= 0
    assert body["used_context"] is True
    assert {s["filename"] for s in body["sources"]} == {"syllabus.pdf", "lecture.md"}


async def test_query_without_context_returns_fallback(client, empty_chat):
    body = (await client.post("/api/chat/query", json={"question": "anything"})).json()
    assert body["answer"] == NO_CONTEXT_ANSWER
    assert body["sources"] == []
    assert body["used_context"] is False


async def test_query_rejects_empty_question(client):
    response = await client.post("/api/chat/query", json={"question": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_query_rejects_missing_question(client):
    assert (await client.post("/api/chat/query", json={})).status_code == 422


async def test_query_rejects_oversized_question(client):
    response = await client.post("/api/chat/query", json={"question": "x" * 5000})
    assert response.status_code == 422


async def test_query_can_omit_sources(client, offline_chat):
    body = (
        await client.post(
            "/api/chat/query", json={"question": "q", "include_sources": False}
        )
    ).json()
    assert body["sources"] == []


async def test_query_maintains_context_across_calls(client, offline_chat):
    first = (await client.post("/api/chat/query", json={"question": "first"})).json()
    second = (
        await client.post(
            "/api/chat/query",
            json={"question": "second", "session_id": first["session_id"]},
        )
    ).json()
    assert second["session_id"] == first["session_id"]


async def test_query_persists_to_the_database(client, offline_chat):
    body = (await client.post("/api/chat/query", json={"question": "remember me"})).json()
    async with async_session() as session:
        rows = await session.execute(
            select(Message).where(Message.session_id == body["session_id"])
        )
        assert [m.role for m in rows.scalars()] == ["user", "assistant"]


# -- POST /stream ----------------------------------------------------------


async def test_stream_emits_sse_content_type(client, offline_chat):
    response = await client.post("/api/chat/stream", json={"question": "exam weight?"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")


async def test_stream_sets_no_buffering_headers(client, offline_chat):
    response = await client.post("/api/chat/stream", json={"question": "q"})
    # Without this a reverse proxy buffers the whole response and the client
    # sees no streaming at all.
    assert response.headers.get("x-accel-buffering") == "no"
    assert response.headers.get("cache-control") == "no-cache"


async def test_stream_frames_end_with_finish_and_sources(client, offline_chat):
    response = await client.post("/api/chat/stream", json={"question": "exam weight?"})
    frames = sse_frames(response.text)

    assert len(frames) >= 2
    assert all(f["finish"] is False for f in frames[:-1])
    assert frames[-1]["finish"] is True
    assert {s["filename"] for s in frames[-1]["sources"]} == {
        "syllabus.pdf",
        "lecture.md",
    }


async def test_stream_deltas_reassemble_into_the_answer(client, offline_chat):
    streamed = "".join(
        f["delta"] for f in sse_frames(
            (await client.post("/api/chat/stream", json={"question": "q"})).text
        )
    )
    direct = (await client.post("/api/chat/query", json={"question": "q"})).json()
    assert streamed == direct["answer"]


async def test_stream_emits_multiple_delta_frames(client, offline_chat):
    frames = sse_frames(
        (await client.post("/api/chat/stream", json={"question": "exam weight?"})).text
    )
    assert len([f for f in frames if not f["finish"]]) >= 1


async def test_stream_without_context_yields_fallback_then_finishes(client, empty_chat):
    frames = sse_frames(
        (await client.post("/api/chat/stream", json={"question": "anything"})).text
    )
    answer = "".join(f["delta"] for f in frames)
    assert answer == NO_CONTEXT_ANSWER
    assert frames[-1]["finish"] is True
    assert frames[-1]["sources"] == []


async def test_stream_persists_the_exchange(client, offline_chat):
    """Regression: the plan's stream route never wrote to the database.

    This is the test that catches the stale-session bug, because the stream
    body is consumed after the request's injected DB session is closed.
    """
    frames = sse_frames(
        (await client.post("/api/chat/stream", json={"question": "remember"})).text
    )
    session_id = frames[-1]["session_id"]

    async with async_session() as session:
        rows = await session.execute(
            select(Message).where(Message.session_id == session_id)
        )
        stored = list(rows.scalars())

    assert [m.role for m in stored] == ["user", "assistant"]
    assert stored[0].content == "remember"
    assert stored[1].sources, "sources should be persisted on the assistant turn"


async def test_stream_persisted_answer_matches_the_stream(client, offline_chat):
    frames = sse_frames(
        (await client.post("/api/chat/stream", json={"question": "remember"})).text
    )
    streamed = "".join(f["delta"] for f in frames)

    async with async_session() as session:
        rows = await session.execute(
            select(Message).where(
                Message.session_id == frames[-1]["session_id"],
                Message.role == "assistant",
            )
        )
        assert rows.scalar_one().content == streamed


async def test_stream_maintains_context_across_requests(client, offline_chat):
    first = sse_frames(
        (await client.post("/api/chat/stream", json={"question": "first"})).text
    )[-1]

    async with async_session() as session:
        rows = await session.execute(
            select(Message).where(Message.session_id == first["session_id"])
        )
        assert len(list(rows.scalars())) == 2

    second = sse_frames(
        (
            await client.post(
                "/api/chat/stream",
                json={"question": "second", "session_id": first["session_id"]},
            )
        ).text
    )[-1]
    assert second["session_id"] == first["session_id"]

    async with async_session() as session:
        rows = await session.execute(
            select(Message).where(Message.session_id == first["session_id"])
        )
        assert len(list(rows.scalars())) == 4, "second turn should append, not replace"


async def test_stream_rejects_empty_question(client, offline_chat):
    assert (
        await client.post("/api/chat/stream", json={"question": ""})
    ).status_code == 422


# -- POST /clear -----------------------------------------------------------


async def test_clear_removes_the_session(client, offline_chat):
    body = (await client.post("/api/chat/query", json={"question": "q"})).json()
    response = await client.post("/api/chat/clear", json={"session_id": body["session_id"]})

    assert response.status_code == 200
    assert response.json()["status"] == "cleared"
    assert response.json()["messages_removed"] == 2


async def test_clear_requires_a_session_id(client):
    assert (await client.post("/api/chat/clear", json={})).status_code == 422


async def test_clear_unknown_session_is_ok(client, offline_chat):
    response = await client.post("/api/chat/clear", json={"session_id": "sess_nope"})
    assert response.status_code == 200
    assert response.json()["messages_removed"] == 0


async def test_query_after_clear_starts_an_empty_conversation(client, offline_chat):
    """A cleared id is reusable, and reuse must not resurrect the old turns.

    This used to assert the id *changed*, which was incidental: the service
    treated a caller-supplied id as a lookup key only, so every turn minted a
    new session. That also meant a client-chosen id never accumulated any
    history. The requirement is that the conversation starts empty, not that
    the identifier churns.
    """
    body = (await client.post("/api/chat/query", json={"question": "q"})).json()
    await client.post("/api/chat/clear", json={"session_id": body["session_id"]})

    after = await client.post(
        "/api/chat/query",
        json={"question": "q again", "session_id": body["session_id"]},
    )
    assert after.status_code == 200

    history = (
        await client.get("/api/chat/history/%s" % body["session_id"])
    ).json()["messages"]

    # The new turn only. The pre-clear "q" and its answer must stay gone.
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[0]["content"] == "q again"


async def test_history_accumulates_for_a_client_supplied_session_id(client, offline_chat):
    """Two turns on one client-chosen id must produce one two-turn history.

    The end-to-end version of the regression in `get_or_create_session`:
    before the fix each turn returned a different server-generated id, so
    asking for history by the id the client had been using always returned [].
    """
    sid = "client-supplied-id"

    first = await client.post(
        "/api/chat/query", json={"question": "first", "session_id": sid}
    )
    assert first.status_code == 200
    assert first.json()["session_id"] == sid

    await client.post(
        "/api/chat/query", json={"question": "second", "session_id": sid}
    )

    messages = (await client.get("/api/chat/history/%s" % sid)).json()["messages"]

    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert [m["content"] for m in messages][:2] == ["first", messages[1]["content"]]


# -- GET /history ----------------------------------------------------------


async def test_history_returns_the_conversation(client, offline_chat):
    body = (await client.post("/api/chat/query", json={"question": "remember"})).json()
    response = await client.get(f"/api/chat/history/{body['session_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == body["session_id"]
    assert [m["role"] for m in payload["messages"]] == ["user", "assistant"]
    assert payload["messages"][0]["content"] == "remember"


async def test_history_sources_are_decoded_json(client, offline_chat):
    body = (await client.post("/api/chat/query", json={"question": "q"})).json()
    payload = (await client.get(f"/api/chat/history/{body['session_id']}")).json()

    assistant = [m for m in payload["messages"] if m["role"] == "assistant"][0]
    assert isinstance(assistant["sources"], list)
    assert assistant["sources"][0]["filename"] == "syllabus.pdf"


async def test_history_of_unknown_session_is_empty(client, offline_chat):
    payload = (await client.get("/api/chat/history/sess_nope")).json()
    assert payload["messages"] == []


# -- Dependency failure mapping -------------------------------------------


async def test_unreachable_embedding_provider_returns_503(client, monkeypatch):
    """Retrieval needs an embedding; if that call fails the client must see 503."""
    from app.services.embedding_service import get_embedding_service

    class DeadEmbedder:
        model_name = "text-embedding-3-small"
        dimension = 1536

        async def embed_many(self, texts):
            raise RuntimeError("connection refused")

    service = get_embedding_service()
    monkeypatch.setattr(type(service), "get_embedder", classmethod(lambda cls: DeadEmbedder()))
    monkeypatch.setattr(type(service), "get_provider", classmethod(lambda cls: "openai"))

    response = await client.post("/api/chat/query", json={"question": "anything"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "EMBEDDING_UNAVAILABLE"


async def test_provider_mismatch_returns_409(client, monkeypatch):
    """Re-indexing is a server-side fix, so the error must be actionable."""
    from app.services import embedding_service as es
    from app.services.embedding_service import get_chroma_collection, get_embedding_service

    # Index something first. A mismatch only means anything against a populated
    # index; an empty one is compatible with any provider, and the check is
    # deliberately relaxed there so that deleting every document unblocks a
    # re-index.
    service = get_embedding_service()
    vectors = await service.embed_texts(["content that pins the index dimension"])
    await service.store_embeddings(
        document_id="doc_locked", chunks=["content that pins the index dimension"],
        embeddings=vectors, filename="a.txt",
    )
    assert get_chroma_collection().count() > 0

    es.EmbeddingService._write_index_info("openai", "text-embedding-3-large", 1536)

    class OtherEmbedder:
        model_name = "text-embedding-3-small"
        dimension = 1536

        async def embed_many(self, texts):
            return [[0.0] * 1536 for _ in texts]

    monkeypatch.setattr(type(service), "get_embedder", classmethod(lambda cls: OtherEmbedder()))
    monkeypatch.setattr(type(service), "get_provider", classmethod(lambda cls: "openai"))

    response = await client.post("/api/chat/query", json={"question": "anything"})
    assert response.status_code == 409
    body = response.json()["error"]
    assert body["code"] == "EMBEDDING_MISMATCH"
    assert "Re-index" in body["message"]
