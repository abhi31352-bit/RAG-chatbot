"""CORS configuration helper.

`main.py` registers the middleware directly, but exposing the options here
keeps the allowed-origin list in a single, testable place.
"""

from typing import List

from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


def cors_origins() -> List[str]:
    return settings.CORS_ORIGINS


def register_cors(app) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
