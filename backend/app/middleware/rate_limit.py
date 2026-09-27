"""Simple in-memory rate limiting.

This is intentionally lightweight for the class demo. A production system
should use a shared store (e.g. Redis) so limits apply across workers.
"""

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings

WINDOW_SECONDS = 60

# client_ip -> deque of request timestamps
_request_log: "defaultdict[str, deque]" = defaultdict(deque)


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _is_rate_limited(key: str) -> bool:
    """Register a request and return True if the client is over the limit."""
    now = time.time()
    bucket = _request_log[key]

    while bucket and now - bucket[0] > WINDOW_SECONDS:
        bucket.popleft()

    if len(bucket) >= settings.RATE_LIMIT_REQUESTS_PER_MINUTE:
        return True

    bucket.append(now)
    return False


async def rate_limit_middleware(request: Request, call_next):
    if _is_rate_limited(_client_key(request)):
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "RATE_LIMITED",
                    "message": "Too many requests. Please try again shortly.",
                    "details": {
                        "limit": settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
                        "window_seconds": WINDOW_SECONDS,
                    },
                }
            },
            headers={"Retry-After": str(WINDOW_SECONDS)},
        )
    return await call_next(request)


def reset_rate_limits() -> None:
    """Clear all counters. Useful for tests."""
    _request_log.clear()
