"""Shared pytest fixtures."""

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

# Ensure the backend package is importable when running from the repo root.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Redirect runtime data *before* anything imports app.config.
#
# This must happen at conftest import time, not in a fixture: pytest imports
# conftest.py first but then collects test modules, and a test module's
# top-level `from app.config import settings` would freeze the real dev paths
# into `settings` before any fixture ran.
_TEST_DATA_ROOT = tempfile.mkdtemp(prefix="rag-chatbot-tests-")
os.environ["CHROMA_PERSIST_DIR"] = os.path.join(_TEST_DATA_ROOT, "chroma")
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_DATA_ROOT, "uploads")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DATA_ROOT, 'test.db')}"
# Never let a test reach a paid API, whatever key happens to be in .env.
os.environ["EMBEDDING_PROVIDER"] = "local"
os.environ["LLM_PROVIDER"] = "offline"
# Blanked outright rather than relying on LLM_PROVIDER=offline above. Tests
# that set LLM_PROVIDER back to "auto" to exercise provider selection would
# otherwise see a real key from the developer's .env, which both makes billed
# calls and silently changes what "auto" resolves to -- so a test would pass or
# fail depending on whether a local .env happened to be filled in. Tests that
# need a key set it themselves via monkeypatch.
os.environ["OPENAI_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""

atexit.register(shutil.rmtree, _TEST_DATA_ROOT, True)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables():
    """Create the schema once per session.

    The `client` fixture uses ASGITransport, which never runs the app lifespan,
    so table creation cannot be left to `init_db()` at startup.
    """
    from app.models.chat import Message, Session  # noqa: F401
    from app.models.database import Base, engine
    from app.models.document import Chunk, Document  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db_session():
    """Yield an AsyncSession bound to the (already created) test database."""
    from app.models.database import async_session

    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    """An httpx AsyncClient bound to the ASGI app."""
    import httpx

    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def clean_db():
    """Empty every table so a test starts from a known state.

    Chroma is *not* cleared: deleting documents cascades their vectors, and the
    tests that care assert on relative counts.
    """
    from sqlalchemy import delete

    from app.models.chat import Message, Session
    from app.models.database import async_session
    from app.models.document import Chunk, Document

    async with async_session() as session:
        for model in (Message, Chunk, Document, Session):
            await session.execute(delete(model))
        await session.commit()
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.middleware.rate_limit import reset_rate_limits

    reset_rate_limits()
    yield


@pytest.fixture(autouse=True)
def _reset_embedding_service():
    """Drop cached Chroma clients/embedders so no state leaks between tests.

    Also restores the index-info sidecar. Tests that simulate a provider change
    write a foreign model into it, and a stale value survives the Chroma reset
    and then fails every later test with a mismatch -- which reads like a real
    regression rather than leakage. Restoring it here rather than in a
    ``try``/``finally`` per test means a failing assertion cannot leave the
    suite poisoned.
    """
    from app.config import settings
    from app.services.embedding_service import EmbeddingService

    EmbeddingService.reset()
    saved = EmbeddingService._read_index_info()
    yield
    if saved:
        EmbeddingService._write_index_info(
            saved.get("embedding_provider", "local"),
            saved["embedding_model"],
            saved.get("embedding_dimension", settings.LOCAL_EMBEDDING_DIM),
        )
    else:
        EmbeddingService._clear_index_info()
    EmbeddingService.reset()


@pytest.fixture(autouse=True)
def _reset_generator():
    """Drop the cached LLM generator so provider switches take effect."""
    from app.rag.generator import reset_generator

    reset_generator()
    yield
    reset_generator()


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: run test in an event loop")
