"""Pydantic request/response schemas.

These define the API contract consumed by the frontend (see architecture.md
section 5), so field names here and in `types/index.ts` must stay in sync.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class DocumentResponse(BaseModel):
    id: str = Field(..., description="Document identifier, e.g. 'doc_ab12cd34ef56'")
    filename: str
    file_type: str = Field(..., description="Extension without a dot, e.g. 'pdf'")
    file_size: int
    chunk_count: int
    status: str = Field(..., description="pending | processed | failed")
    created_at: str


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int


class ChunkResponse(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    token_count: int
    content: str
    page_number: Optional[int] = None


class DeleteResponse(BaseModel):
    status: str
    id: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class SourceResponse(BaseModel):
    document_id: str
    filename: str
    chunk_index: int
    excerpt: str
    similarity: float = 0.0


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str] = Field(None, max_length=64)
    include_sources: bool = True

    @field_validator("question")
    @classmethod
    def _question_not_blank(cls, value: str) -> str:
        # A whitespace-only question would embed to a zero vector and match
        # nothing, which is a confusing way to say "empty question".
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceResponse] = Field(default_factory=list)
    session_id: str
    processing_time_ms: int
    mode: str = Field(
        ..., description="'openai' or 'offline-extractive'"
    )
    used_context: bool = Field(
        ..., description="False when nothing was retrieved and no model was called"
    )


class ClearChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=64)


class ClearChatResponse(BaseModel):
    status: str
    session_id: str
    messages_removed: int


class ChatMessage(BaseModel):
    role: str
    content: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[ChatMessage]
