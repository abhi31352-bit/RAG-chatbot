"""Health and readiness endpoints."""

import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.config import settings
from app.models.database import engine

logger = logging.getLogger("rag-chatbot")

router = APIRouter()


@router.get("")
async def health_check():
    """Liveness probe. Returns 200 as long as the process is up."""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "llm_model": settings.LLM_MODEL,
    }


async def _check_database() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database readiness check failed")
        return False


async def _check_vector_store() -> bool:
    try:
        from app.services.embedding_service import get_chroma_client

        get_chroma_client().list_collections()
        return True
    except Exception:
        logger.exception("Vector store readiness check failed")
        return False


@router.get("/ready")
async def readiness_check():
    """Readiness probe. Verifies the critical downstream services."""
    checks = {
        "database": await _check_database(),
        "vector_store": await _check_vector_store(),
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
    }
