"""Database engine, session factory, and declarative base."""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

DATABASE_URL = settings.async_database_url

engine = create_async_engine(DATABASE_URL, echo=settings.SQL_ECHO)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """Make SQLite honour `ON DELETE CASCADE`.

    SQLite ignores foreign-key constraints (and therefore cascades) unless
    they are explicitly switched on for the connection. Without this, deleting
    a document silently leaves its chunks behind as orphans.
    """
    if settings.sqlite_path:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


async def get_db():
    """FastAPI dependency that yields a database session."""
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables. Called on application startup."""
    # Import models so they are registered on Base.metadata
    from app.models.chat import Message, Session  # noqa: F401
    from app.models.document import Chunk, Document  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
