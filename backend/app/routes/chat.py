"""Chat routes: non-streaming query, SSE streaming, and session management."""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_chat_service, get_db
from app.exceptions import LLMUnavailableError
from app.models.database import async_session
from app.models.schemas import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ClearChatRequest,
    ClearChatResponse,
)
from app.services.chat_service import ChatService

logger = logging.getLogger("rag-chatbot")

router = APIRouter()

#: SSE headers. `X-Accel-Buffering: no` matters in practice: a reverse proxy
#: will otherwise hold the whole response and the client sees no streaming.
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _frame(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/query", response_model=ChatResponse, summary="Ask a question")
async def chat_query(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    service: ChatService = Depends(get_chat_service),
):
    result = await service.query(
        db=db,
        question=request.question,
        session_id=request.session_id,
        include_sources=request.include_sources,
    )
    return result.to_dict()


@router.post("/stream", summary="Ask a question, streaming the answer via SSE")
async def chat_stream(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
):
    """Stream an answer as Server-Sent Events.

    Note the absence of a `db` dependency. Starlette closes `yield`-based
    dependencies as soon as the endpoint returns, which is *before* the
    StreamingResponse body is consumed -- so a session injected here would
    already be closed by the time the first chunk is generated. The stream
    therefore opens its own session and closes it when iteration finishes.
    """

    async def event_source() -> AsyncGenerator[str, None]:
        try:
            async with async_session() as db:
                async for event in service.stream_query(
                    db=db,
                    question=request.question,
                    session_id=request.session_id,
                    include_sources=request.include_sources,
                ):
                    if event.type == "delta":
                        yield _frame({"delta": event.text, "finish": False})
                    elif event.type == "sources":
                        # Sources ride on the terminal frame; the frontend
                        # renders them once the answer is complete.
                        yield _frame(
                            {
                                "delta": "",
                                "finish": True,
                                "sources": [s.to_dict() for s in event.sources],
                                "session_id": event.session_id,
                                "mode": event.mode,
                            }
                        )
        except LLMUnavailableError as exc:
            # Nothing has been written yet if retrieval failed up front, but a
            # mid-stream failure cannot change the status code, so both cases
            # are reported as a terminal event.
            logger.warning("Stream failed: %s", exc.message)
            yield _frame({"delta": "", "finish": True, "error": exc.message})
        except Exception as exc:
            logger.exception("Unexpected error while streaming")
            yield _frame({"delta": "", "finish": True, "error": str(exc)})

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post(
    "/clear",
    response_model=ClearChatResponse,
    summary="Clear a conversation",
)
async def clear_chat(
    request: ClearChatRequest,
    db: AsyncSession = Depends(get_db),
    service: ChatService = Depends(get_chat_service),
):
    return await service.clear_session(db, request.session_id)


@router.get(
    "/history/{session_id}",
    response_model=ChatHistoryResponse,
    summary="Fetch a conversation's messages",
)
async def chat_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    service: ChatService = Depends(get_chat_service),
):
    messages = await service.get_session_history(db, session_id)
    return {"session_id": session_id, "messages": messages}
