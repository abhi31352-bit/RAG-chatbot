"""Tests for the RAG pipeline and the chat service (sessions + persistence)."""

import json

import pytest
from sqlalchemy import select

from app.models.chat import Message, Session
from app.models.database import async_session
from app.rag.generator import NO_CONTEXT_ANSWER, OfflineGenerator
from app.rag.pipeline import RAGPipeline, Retriever

# -- Fakes -----------------------------------------------------------------


class FakeRetriever:
    """Returns a fixed result set, or raises to simulate failure."""

    def __init__(self, results=None, error=None):
        self.results = results or []
        self.error = error
        self.calls = []

    async def retrieve(self, query, top_k=None, memory_context=None):
        self.calls.append((query, top_k))
        if self.error:
            raise self.error
        return self.results


CHUNKS = [
    {
        "content": "The final examination accounts for 40 percent of the grade.",
        "metadata": {"document_id": "doc_1", "filename": "syllabus.pdf", "chunk_index": 0},
        "similarity": 0.8,
    },
    {
        "content": "A second chunk from the same document.",
        "metadata": {"document_id": "doc_1", "filename": "syllabus.pdf", "chunk_index": 1},
        "similarity": 0.6,
    },
    {
        "content": "Week 1 covers linear regression.",
        "metadata": {"document_id": "doc_2", "filename": "lecture.md", "chunk_index": 0},
        "similarity": 0.3,
    },
]


# -- Source formatting -----------------------------------------------------


def test_sources_dedupe_by_document():
    """Three chunks across two documents should cite two documents."""
    pipeline = RAGPipeline(retriever=FakeRetriever())
    sources = pipeline.format_sources(CHUNKS)
    assert [s.filename for s in sources] == ["syllabus.pdf", "lecture.md"]


def test_sources_keep_the_best_chunk_per_document():
    pipeline = RAGPipeline(retriever=FakeRetriever())
    sources = pipeline.format_sources(CHUNKS)
    assert sources[0].chunk_index == 0, "the higher-scoring chunk should be kept"
    assert sources[0].similarity == pytest.approx(0.8)


def test_source_excerpt_is_truncated():
    long_chunk = [
        {
            "content": "x" * 5000,
            "metadata": {"document_id": "doc_x", "filename": "big.txt"},
        }
    ]
    pipeline = RAGPipeline(retriever=FakeRetriever())
    excerpt = pipeline.format_sources(long_chunk)[0].excerpt
    assert len(excerpt) < 500
    assert excerpt.endswith("...")


def test_source_excerpt_keeps_short_text_whole():
    pipeline = RAGPipeline(retriever=FakeRetriever())
    assert not pipeline.format_sources(CHUNKS)[0].excerpt.endswith("...")


def test_format_sources_tolerates_missing_metadata():
    pipeline = RAGPipeline(retriever=FakeRetriever())
    sources = pipeline.format_sources([{"content": "text", "metadata": {}}])
    assert sources[0].filename == "Unknown"
    assert sources[0].document_id == "unknown"


def test_format_sources_of_empty_is_empty():
    assert RAGPipeline(retriever=FakeRetriever()).format_sources([]) == []


# -- Query -----------------------------------------------------------------


async def test_query_returns_answer_and_sources():
    pipeline = RAGPipeline(retriever=FakeRetriever(CHUNKS))
    result = await pipeline.query("How much is the exam worth?")
    assert "40 percent" in result.answer
    assert len(result.sources) == 2
    assert result.used_context is True


async def test_query_passes_configured_top_k():
    retriever = FakeRetriever(CHUNKS)
    pipeline = RAGPipeline(retriever=retriever)
    await pipeline.query("question")
    assert retriever.calls[0][1] == settings_top_k()


def settings_top_k():
    from app.config import settings

    return settings.TOP_K_RETRIEVAL


async def test_query_without_results_skips_the_model():
    """An empty index must not reach the LLM -- that is how hallucinations start."""
    pipeline = RAGPipeline(retriever=FakeRetriever([]))
    result = await pipeline.query("anything at all")
    assert result.answer == NO_CONTEXT_ANSWER
    assert result.sources == []
    assert result.used_context is False


async def test_query_forwards_history_to_the_prompt():
    seen = {}

    class SpyGenerator(OfflineGenerator):
        async def generate(self, prompt):
            seen["prompt"] = prompt
            return "answer"

    pipeline = RAGPipeline(
        retriever=FakeRetriever(CHUNKS), generator=SpyGenerator()
    )
    await pipeline.query("follow up", [{"role": "user", "content": "earlier"}])
    assert "earlier" in seen["prompt"]


# -- Streaming -------------------------------------------------------------


async def test_stream_emits_deltas_then_sources():
    pipeline = RAGPipeline(retriever=FakeRetriever(CHUNKS))
    events = [e async for e in pipeline.query_stream("question")]

    assert [e.type for e in events] == ["delta"] * (
        len(events) - 1
    ) + ["sources"]
    assert events[-1].sources and events[-1].sources[0].filename == "syllabus.pdf"


async def test_stream_without_results_ends_with_empty_sources():
    pipeline = RAGPipeline(retriever=FakeRetriever([]))
    events = [e async for e in pipeline.query_stream("question")]

    assert len(events) == 2
    assert events[0].text == NO_CONTEXT_ANSWER
    assert events[1].type == "sources" and events[1].sources == []


async def test_stream_deltas_concatenate_into_the_answer():
    pipeline = RAGPipeline(retriever=FakeRetriever(CHUNKS))
    events = [e async for e in pipeline.query_stream("question")]
    joined = "".join(e.text for e in events if e.type == "delta")
    assert joined == (await pipeline.query("question")).answer


# -- Retriever -------------------------------------------------------------


async def test_retriever_returns_empty_for_blank_query():
    assert await Retriever().retrieve("   ") == []


async def test_retriever_reports_empty_index(client):
    """With nothing indexed, retrieval yields nothing rather than erroring."""
    assert await Retriever().retrieve("any question at all") == []


# -- Chat service: sessions ------------------------------------------------


async def test_query_creates_a_session(db_session):
    from app.services.chat_service import ChatService

    result = await ChatService().query(db_session, "How much is the exam worth?")
    assert result.session_id.startswith("sess_")


async def test_query_reuses_the_given_session(db_session):
    from app.services.chat_service import ChatService

    service = ChatService()
    first = await service.query(db_session, "first question")
    second = await service.query(db_session, "second question", session_id=first.session_id)
    assert second.session_id == first.session_id


async def test_query_with_unknown_session_recovers_rather_than_failing(db_session):
    """A stale id (e.g. after /clear) must not 404.

    The invariant is recovery, not a fresh id. It used to also assert that the
    id *changed*, which is what `get_or_create_session` happened to do: it used
    the caller's id as a lookup key only, then created the replacement session
    under a generated id. No client depends on that churn -- the web UI drops
    its stored id on clear -- so the assertion was pinning a side effect rather
    than a requirement, and it hid the fact that a client-chosen id was being
    ignored on its very first turn too.
    """
    from app.services.chat_service import ChatService

    service = ChatService()
    result = await service.query(db_session, "q", session_id="sess_gone")

    history = await service.get_session_history(db_session, "sess_gone")
    assert [m["content"] for m in history] == ["q", NO_CONTEXT_ANSWER]
    assert result.session_id == "sess_gone"


async def test_query_persists_both_messages(db_session):
    from app.services.chat_service import ChatService

    result = await ChatService().query(db_session, "What is the exam worth?")
    messages = await ChatService().get_session_history(db_session, result.session_id)

    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"] == "What is the exam worth?"


async def test_sources_are_stored_as_valid_json(db_session):
    """A Python repr would not survive JSON.parse on the client."""
    from app.services.chat_service import ChatService

    service = ChatService()
    service._pipeline = RAGPipeline(retriever=FakeRetriever(CHUNKS))
    result = await service.query(db_session, "question")

    async with async_session() as session:
        stored = await session.execute(
            select(Message).where(Message.session_id == result.session_id)
        )
        assistant = [m for m in stored.scalars() if m.role == "assistant"][0]

    assert assistant.sources
    parsed = json.loads(assistant.sources)  # would raise on a repr
    assert parsed[0]["filename"] == "syllabus.pdf"


async def test_history_takes_the_most_recent_turns(db_session, monkeypatch):
    """The old code took the *oldest* N, starving the model of recent context."""
    from app.config import settings
    from app.services.chat_service import ChatService

    monkeypatch.setattr(settings, "MAX_HISTORY_MESSAGES", 4)
    service = ChatService()
    service._pipeline = RAGPipeline(retriever=FakeRetriever([]))

    session_id = None
    for i in range(5):
        result = await service.query(db_session, f"turn {i}", session_id=session_id)
        session_id = result.session_id

    history = await service.get_conversation_history(db_session, session_id)
    # History alternates user/assistant, so 4 messages is the last 2 turns.
    assert len(history) == 4
    asked = [m["content"] for m in history if m["role"] == "user"]
    assert asked == ["turn 3", "turn 4"], "the oldest turns should be dropped"
    assert history[-1]["role"] == "assistant"


async def test_history_does_not_include_the_current_question(db_session, monkeypatch):
    """The prompt already contains the question; history must not repeat it."""
    from app.config import settings
    from app.services.chat_service import ChatService

    monkeypatch.setattr(settings, "MAX_HISTORY_MESSAGES", 10)
    service = ChatService()
    service._pipeline = RAGPipeline(retriever=FakeRetriever([]))

    session = await service.get_or_create_session(db_session)
    await service.query(db_session, "old question", session_id=session.id)

    history = await service.get_conversation_history(db_session, session.id)
    assert [m["content"] for m in history] == ["old question", NO_CONTEXT_ANSWER]


async def test_message_count_is_tracked(db_session):
    from app.services.chat_service import ChatService

    service = ChatService()
    result = await service.query(db_session, "a question")
    async with async_session() as session:
        row = await session.execute(
            select(Session).where(Session.id == result.session_id)
        )
        assert row.scalar_one().message_count == 2


# -- Chat service: client-chosen session ids -------------------------------


async def test_a_client_chosen_session_id_is_honoured(db_session):
    """A caller-supplied id must become the session's id, not just a lookup key.

    The service used to look the id up, fail to find it, and then create a
    session under a *generated* id. The caller was handed a different id than
    the one it asked for, so every turn looked like a first turn.
    """
    from app.services.chat_service import ChatService

    service = ChatService()
    result = await service.query(db_session, "a question", session_id="client-chosen-id")

    assert result.session_id == "client-chosen-id"
    async with async_session() as session:
        row = await session.execute(
            select(Session).where(Session.id == "client-chosen-id")
        )
        assert row.scalar_one_or_none() is not None


async def test_history_accumulates_across_turns_on_a_client_chosen_id(db_session):
    """The failure this caused was silent: history was always empty.

    A client that holds its own id across requests -- the whole point of the
    parameter -- got a 200 every time and an empty conversation back.
    """
    from app.services.chat_service import ChatService

    service = ChatService()
    await service.query(db_session, "first question", session_id="pinned-id")
    await service.query(db_session, "second question", session_id="pinned-id")

    history = await service.get_session_history(db_session, "pinned-id")

    assert [m["content"] for m in history] == [
        "first question", NO_CONTEXT_ANSWER, "second question", NO_CONTEXT_ANSWER,
    ]


async def test_repeated_turns_do_not_multiply_session_rows(db_session):
    """One conversation must be one row.

    Before the fix each turn created a fresh session, so a client holding a
    fixed id grew the table by a row per question and the messages were
    scattered across conversations that could never be read back together.
    """
    from app.services.chat_service import ChatService

    service = ChatService()
    for i in range(3):
        await service.query(db_session, "question %d" % i, session_id="stable-id")

    async with async_session() as session:
        # Scoped by id rather than counting the table: the session-scoped
        # database is shared across tests in this file, so a bare count would
        # measure the whole suite.
        rows = (
            await session.execute(select(Session).where(Session.id == "stable-id"))
        ).scalars().all()
        messages = (
            await session.execute(select(Message).where(Message.session_id == "stable-id"))
        ).scalars().all()

    assert len(rows) == 1
    # Three questions and three answers, all on that one conversation.
    assert len(messages) == 6


async def test_clearing_a_client_chosen_session_removes_its_messages(db_session):
    """Clear is symmetrical with query only if the id round-trips."""
    from app.services.chat_service import ChatService

    service = ChatService()
    await service.query(db_session, "a question", session_id="to-be-cleared")

    cleared = await service.clear_session(db_session, "to-be-cleared")

    assert cleared["messages_removed"] == 2
    assert await service.get_session_history(db_session, "to-be-cleared") == []


async def test_an_id_is_still_generated_when_none_is_supplied(db_session):
    from app.services.chat_service import ChatService

    service = ChatService()
    result = await service.query(db_session, "a question")

    assert result.session_id.startswith("sess_")


async def test_a_stale_id_starts_a_fresh_rather_than_failing(db_session):
    """After a clear the client keeps its id; the next question must recover."""
    from app.services.chat_service import ChatService

    service = ChatService()
    await service.query(db_session, "a question", session_id="recycled")
    await service.clear_session(db_session, "recycled")

    result = await service.query(db_session, "a new question", session_id="recycled")

    assert result.session_id == "recycled"
    history = await service.get_session_history(db_session, "recycled")
    # Fresh, not appended: the cleared messages must not come back.
    assert [m["content"] for m in history] == ["a new question", NO_CONTEXT_ANSWER]
async def test_save_message_rejects_unknown_role(db_session):
    from app.services.chat_service import ChatService

    service = ChatService()
    session = await service.get_or_create_session(db_session)
    with pytest.raises(ValueError):
        await service._save_message(db_session, session.id, "system", "hi")


# -- Chat service: streaming ----------------------------------------------


async def test_stream_persists_the_exchange(db_session):
    """Regression: the plan's /stream bypassed persistence entirely."""
    from app.services.chat_service import ChatService

    service = ChatService()
    service._pipeline = RAGPipeline(retriever=FakeRetriever(CHUNKS))

    events = [e async for e in service.stream_query(db_session, "a question")]

    # The service creates the session, so take the id from its own events.
    history = await service.get_session_history(db_session, events[0].session_id)
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert events[-1].type == "sources"


async def test_stream_persists_the_assembled_answer(db_session):
    from app.services.chat_service import ChatService

    service = ChatService()
    service._pipeline = RAGPipeline(retriever=FakeRetriever(CHUNKS))

    events = [e async for e in service.stream_query(db_session, "a question")]
    assembled = "".join(e.text for e in events if e.type == "delta")

    history = await service.get_session_history(db_session, events[0].session_id)
    assistant = [m for m in history if m["role"] == "assistant"][0]
    assert assistant["content"] == assembled


async def test_stream_maintains_context_across_turns(db_session):
    """A follow-up in a streamed conversation must see the earlier turn."""
    from app.services.chat_service import ChatService

    service = ChatService()
    service._pipeline = RAGPipeline(retriever=FakeRetriever([]))
    first = [e async for e in service.stream_query(db_session, "first question")]

    seen = {}
    original = service._pipeline.query_stream

    async def spy(question, history=None):
        seen["history"] = history
        async for e in original(question, history):
            yield e

    service._pipeline.query_stream = spy
    second = [e async for e in service.stream_query(db_session, "second question",
                                                    session_id=first[0].session_id)]

    assert "first question" in [m["content"] for m in seen["history"]]
    assert "second question" not in [m["content"] for m in seen["history"]]
    assert second[-1].session_id == first[0].session_id


async def test_stream_reports_the_same_session_on_every_event(db_session):
    from app.services.chat_service import ChatService

    service = ChatService()
    service._pipeline = RAGPipeline(retriever=FakeRetriever(CHUNKS))
    events = [e async for e in service.stream_query(db_session, "q")]
    assert len({e.session_id for e in events}) == 1


async def test_include_sources_false_still_persists_the_answer(db_session):
    from app.services.chat_service import ChatService

    service = ChatService()
    service._pipeline = RAGPipeline(retriever=FakeRetriever(CHUNKS))
    result = await service.query(
        db_session, "question", include_sources=False
    )
    assert result.sources == []
    assert result.answer


# -- Clearing --------------------------------------------------------------


async def test_clear_removes_messages_and_session(db_session):
    from app.services.chat_service import ChatService

    service = ChatService()
    result = await service.query(db_session, "a question")
    cleared = await service.clear_session(db_session, result.session_id)

    assert cleared["status"] == "cleared"
    assert cleared["messages_removed"] == 2

    async with async_session() as session:
        rows = await session.execute(
            select(Message).where(Message.session_id == result.session_id)
        )
        assert rows.scalars().all() == []

        session_rows = await session.execute(
            select(Session).where(Session.id == result.session_id)
        )
        assert session_rows.scalar_one_or_none() is None


async def test_clear_unknown_session_is_harmless(db_session):
    from app.services.chat_service import ChatService

    result = await ChatService().clear_session(db_session, "sess_nope")
    assert result["messages_removed"] == 0
    assert result["status"] == "cleared"
