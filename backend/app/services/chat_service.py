"""Chat orchestration: sessions, history, and the RAG pipeline.

Every turn -- streamed or not -- persists the user's question and the
assistant's answer. That matters for context: if streamed turns were not
saved, the follow-up question in a streamed conversation would have no history
to build on.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.chat import Message, Session, generate_id
from app.rag.generator import NO_CONTEXT_ANSWER
from app.rag.pipeline import RAGPipeline, Source

logger = logging.getLogger("rag-chatbot")

#: Roles that may appear in persisted history.
ROLES = ("user", "assistant")


@dataclass
class ChatResult:
    answer: str
    sources: List[Source] = field(default_factory=list)
    session_id: str = ""
    mode: str = ""
    used_context: bool = True
    processing_time_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "sources": [s.to_dict() for s in self.sources],
            "session_id": self.session_id,
            "mode": self.mode,
            "used_context": self.used_context,
            "processing_time_ms": self.processing_time_ms,
        }


@dataclass
class ChatStreamEvent:
    """One SSE frame's worth of a streamed turn."""

    type: str  # "delta" | "sources"
    text: str = ""
    sources: List[Source] = field(default_factory=list)
    session_id: str = ""
    mode: str = ""


class ChatService:
    """Runs chat turns and maintains conversation state."""

    def __init__(self, pipeline: Optional[RAGPipeline] = None):
        self._pipeline = pipeline

    @property
    def pipeline(self) -> RAGPipeline:
        # Built on first use: constructing it resolves the LLM provider, and
        # doing that at import time would tie app startup to credentials.
        if self._pipeline is None:
            self._pipeline = RAGPipeline()
        return self._pipeline

    # -- Public API ------------------------------------------------------

    async def query(
        self,
        db: AsyncSession,
        question: str,
        session_id: Optional[str] = None,
        include_sources: bool = True,
    ) -> ChatResult:
        """Answer `question` and persist the exchange."""
        started = time.perf_counter()

        session = await self.get_or_create_session(db, session_id)
        # History is read before the new question is stored, so the prompt
        # never contains the question being answered.
        history = await self.get_conversation_history(db, session.id)

        await self._save_message(db, session.id, "user", question)

        result = await self.pipeline.query(question, history)
        sources = result.sources if include_sources else []

        await self._save_message(
            db, session.id, "assistant", result.answer, sources
        )
        await self._touch_session(db, session)

        elapsed = int((time.perf_counter() - started) * 1000)
        logger.info(
            "Chat turn in %dms (mode=%s, sources=%d, session=%s)",
            elapsed,
            result.mode,
            len(sources),
            session.id,
        )

        return ChatResult(
            answer=result.answer,
            sources=sources,
            session_id=session.id,
            mode=result.mode,
            used_context=result.used_context,
            processing_time_ms=elapsed,
        )

    async def stream_query(
        self,
        db: AsyncSession,
        question: str,
        session_id: Optional[str] = None,
        include_sources: bool = True,
    ) -> AsyncGenerator[ChatStreamEvent, None]:
        """Answer `question`, yielding deltas and persisting the exchange.

        The caller owns `db` and must keep the session open for the whole
        iteration -- see `routes.chat` for why.
        """
        session = await self.get_or_create_session(db, session_id)
        history = await self.get_conversation_history(db, session.id)

        await self._save_message(db, session.id, "user", question)

        answer_parts: List[str] = []
        sources: List[Source] = []
        mode = self.pipeline.mode

        async for event in self.pipeline.query_stream(question, history):
            if event.type == "delta":
                answer_parts.append(event.text)
                yield ChatStreamEvent(
                    type="delta", text=event.text, session_id=session.id, mode=mode
                )
            elif event.type == "sources":
                sources = event.sources if include_sources else []
                yield ChatStreamEvent(
                    type="sources",
                    sources=sources,
                    session_id=session.id,
                    mode=mode,
                )

        # Persist only after the stream finishes, so a cancelled or failed
        # generation does not leave a half-written answer in history.
        answer = "".join(answer_parts) or NO_CONTEXT_ANSWER
        await self._save_message(db, session.id, "assistant", answer, sources)
        await self._touch_session(db, session)

    async def clear_session(self, db: AsyncSession, session_id: str) -> Dict[str, Any]:
        """Delete a session and its messages.

        The session row itself is removed, so the id is dead afterwards and the
        client should start a new conversation.
        """
        result = await db.execute(
            select(func.count(Message.id)).where(Message.session_id == session_id)
        )
        removed = result.scalar() or 0

        await db.execute(delete(Message).where(Message.session_id == session_id))
        await db.execute(delete(Session).where(Session.id == session_id))
        await db.commit()

        logger.info("Cleared session %s (%d messages)", session_id, removed)
        return {"status": "cleared", "session_id": session_id, "messages_removed": removed}

    async def get_session_history(
        self, db: AsyncSession, session_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Full history for a session, oldest first."""
        limit = limit or settings.MAX_HISTORY_MESSAGES * 10
        rows = await self._fetch_messages(db, session_id, limit=limit)
        return [
            {
                "role": m.role,
                "content": m.content,
                "sources": _load_sources(m.sources),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in rows
        ]

    # -- Internals -------------------------------------------------------

    async def get_or_create_session(
        self, db: AsyncSession, session_id: Optional[str] = None
    ) -> Session:
        """Return the named session, or create one under that name.

        An unknown id yields a fresh session rather than a 404: a client that
        kept a stale id after clearing should recover on its next question.

        A caller-supplied id is honoured as the new session's id, not merely
        used as a lookup key. `ChatRequest.session_id` is documented as an
        optional client-chosen id, so a client that generates its own -- which
        is the only way to have an id before the first response arrives, and
        what makes the clear and history endpoints symmetric -- would
        otherwise be handed a different id than the one it asked for. That
        loses the conversation silently: every turn looks like a first turn,
        history comes back empty, and a new session row is written each time,
        so the table grows without bound. The browser UI hides this by
        adopting the id from the response, which is why it went unnoticed.
        """
        if session_id:
            result = await db.execute(
                select(Session).where(Session.id == session_id)
            )
            session = result.scalar_one_or_none()
            if session is not None:
                return session
            logger.info("Unknown session %s; starting a new one", session_id)

        session = Session(id=session_id or generate_id("sess"))
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def get_conversation_history(
        self, db: AsyncSession, session_id: str
    ) -> List[Dict[str, str]]:
        """The most recent turns, oldest first, for prompt building.

        Ordering matters: `created_at` alone is not enough to take a *tail*,
        so the newest N ids are selected first and then re-read in order.
        """
        limit = settings.MAX_HISTORY_MESSAGES
        rows = await self._fetch_messages(db, session_id, limit=limit)
        return [{"role": m.role, "content": m.content} for m in rows]

    async def _fetch_messages(
        self, db: AsyncSession, session_id: str, limit: int
    ) -> List[Message]:
        newest = (
            select(Message.id)
            .where(Message.session_id == session_id)
            # `id` breaks ties so two messages written in the same microsecond
            # keep a stable order.
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        result = await db.execute(
            select(Message)
            .where(Message.id.in_(newest))
            .order_by(Message.created_at, Message.id)
        )
        return list(result.scalars().all())

    async def _save_message(
        self,
        db: AsyncSession,
        session_id: str,
        role: str,
        content: str,
        sources: Optional[Sequence[Source]] = None,
    ) -> Message:
        if role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}, got {role!r}")

        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            # JSON, not str(): a Python repr of a list of dicts uses single
            # quotes and would not survive JSON.parse on the client.
            sources=json.dumps([s.to_dict() for s in sources]) if sources else None,
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
        return message

    async def _touch_session(self, db: AsyncSession, session: Session) -> None:
        result = await db.execute(
            select(func.count(Message.id)).where(Message.session_id == session.id)
        )
        session.message_count = result.scalar() or 0
        session.last_active = session.last_active  # onupdate handles the stamp
        await db.commit()


def _load_sources(raw: Optional[str]) -> List[Dict[str, Any]]:
    """Decode the JSON sources column, tolerating legacy or corrupt values."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("Discarding unparseable sources column: %r", raw[:80])
        return []
    return parsed if isinstance(parsed, list) else []


_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Return the shared ChatService instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
