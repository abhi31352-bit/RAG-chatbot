"""Application entry point."""

import logging
from contextlib import asynccontextmanager

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.exceptions import register_exception_handlers
from app.middleware.cors import register_cors
from app.middleware.logging import logging_middleware
from app.middleware.rate_limit import rate_limit_middleware
from app.models.database import init_db
from app.routes import chat, documents, health

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("rag-chatbot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create data directories and database tables
    settings.ensure_directories()
    await init_db()
    logger.info("%s started (%s)", settings.APP_NAME, settings.APP_ENV)
    yield
    # Shutdown
    logger.info("%s shutting down", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="RAG Chatbot for Class Demo",
    lifespan=lifespan,
)

register_cors(app)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(logging_middleware)
register_exception_handlers(app)

app.include_router(health.router, prefix="/api/health", tags=["Health"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])


# Serve the built React/Vite frontend from frontend/dist.
# On Render, FRONTEND_DIST=../frontend/dist is passed via the start command.
# Resolve relative to the CWD (backend/) so the path works in any deployment.
_frontend_dist_env = os.environ.get("FRONTEND_DIST", "../frontend/dist")
FRONTEND_DIST = Path(_frontend_dist_env).resolve()

if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """Serve the SPA for any non-API route."""
        # API routes are already registered above and take precedence.
        # This catch-all only fires for non-API paths.
        file_path = FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")
