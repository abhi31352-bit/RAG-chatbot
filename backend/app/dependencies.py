"""Reusable FastAPI dependencies."""

from app.models.database import get_db
from app.services.chat_service import get_chat_service
from app.services.document_service import get_document_service
from app.services.embedding_service import get_embedding_service

__all__ = [
    "get_db",
    "get_chat_service",
    "get_document_service",
    "get_embedding_service",
]
