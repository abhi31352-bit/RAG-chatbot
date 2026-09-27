"""Request logging middleware."""

import logging
import time

from fastapi import Request

logger = logging.getLogger("rag-chatbot")


async def logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    logger.info(
        "%s %s -> %s (%.1fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration * 1000,
    )
    return response
