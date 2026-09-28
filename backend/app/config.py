"""Application configuration.

Settings are loaded from environment variables, falling back to the values
in `.env` (see `.env.example`). Never hardcode secrets in this file.
"""

from pathlib import Path
from typing import List, Optional, Tuple

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent


def resolve_path(path: str) -> str:
    """Resolve a relative data path against the backend directory.

    Without this, paths would depend on the current working directory, so
    running `uvicorn` from the repo root would scatter data across the tree.
    Absolute paths are returned unchanged.
    """
    p = Path(path)
    if p.is_absolute():
        return str(p)
    return str((BACKEND_DIR / p).resolve())


def usable_api_key(value: Optional[str]) -> bool:
    """Whether `value` looks like a real key rather than a copied stub.

    Every API key setting goes through this, so that a key left at the
    ``.env.example`` placeholder is treated as *absent*. The consequence is
    that a freshly copied config produces no auth errors and makes no billed
    calls: the app simply stays on its offline path. The cost is that a real
    key containing "your-key" would be silently ignored, which is why this
    matches on obvious stubs only rather than trying to validate a format.
    """
    key = (value or "").strip()
    if not key:
        return False
    lowered = key.lower()
    return "your-key" not in lowered and not lowered.startswith("sk-your")


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "RAG Chatbot"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # OpenAI
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "big-pickle"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Base URL for both the chat and embedding clients. Empty means the SDK
    # default (api.openai.com). Set it to point at any OpenAI-compatible
    # endpoint -- a gateway, a proxy, or a self-hosted server -- which is the
    # only way to use a model name that OpenAI itself does not serve.
    #
    # It is applied to the embedding client too, deliberately: an endpoint that
    # serves one usually serves both, and a key valid for the chat endpoint but
    # not the embedding one is a confusing failure to debug. Because changing
    # the provider changes the vector width, switching this on a populated index
    # still requires re-uploading the documents (EMBEDDING_MISMATCH, 409).
    OPENAI_BASE_URL: str = ""

    # Groq
    #
    # Groq is an inference endpoint only: it serves chat completions on an
    # OpenAI-compatible API but is not where embeddings come from. The two are
    # therefore configured independently -- a Groq key changes what writes the
    # answers and leaves the vector store (local by default) untouched, so
    # adding it can never invalidate an existing index.
    GROQ_API_KEY: str = ""
    # Groq's OpenAI-compatible endpoint. Baked in as a default so the only
    # thing to configure is the key.
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

    # Embeddings
    # auto  -> OpenAI when a usable key is present, otherwise the local
    #          dependency-free embedder (keeps the demo working offline)
    # openai -> force OpenAI
    # local -> force the local embedder
    EMBEDDING_PROVIDER: str = "auto"

    # Signed hashing means two features landing in the same bucket with equal
    # counts and opposite signs cancel exactly, which makes the term *completely*
    # unretrievable rather than merely noisy. At 512 dimensions the 160-feature
    # syllabus chunk had 24 collisions, 9 of which cancelled -- "homework" was
    # annihilated by "trees" and a question about homework retrieved nothing.
    # 2048 dimensions removes the collisions for a realistic document; the cost
    # is 4x the floats, which is irrelevant at this scale. Cancellation is still
    # possible, just far less likely, so `tests/test_embedding.py` asserts that
    # a term present in a document stays findable.
    LOCAL_EMBEDDING_DIM: int = 2048
    EMBEDDING_BATCH_SIZE: int = 100
    EMBEDDING_CACHE_SIZE: int = 2048

    # Vector Store
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_COLLECTION_NAME: str = "course_documents"

    # Database
    DATABASE_URL: str = "sqlite:///./data/app.db"
    # Log every SQL statement. Off by default: DEBUG does not imply this,
    # because the statement log drowns out everything useful.
    SQL_ECHO: bool = False

    # Uploads
    UPLOAD_DIR: str = "./data/uploads"

    # Document Processing
    MAX_FILE_SIZE_MB: int = 50
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    TOP_K_RETRIEVAL: int = 5
    # Chunks scoring worse than this cosine distance are dropped.
    MAX_RETRIEVAL_DISTANCE: float = 1.0

    # LLM Settings
    # auto  -> OpenAI when a usable key is present, otherwise the offline
    #          extractive responder (keeps the demo working without a key)
    # openai -> force OpenAI
    # offline -> force the extractive responder
    LLM_PROVIDER: str = "auto"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 1024
    LLM_TIMEOUT_SECONDS: int = 30
    # Prior turns fed back to the model (user+assistant pairs).
    MAX_HISTORY_MESSAGES: int = 10
    # Recent memory messages used to augment the query before retrieval.
    # This helps resolve follow-up questions (e.g. "What about homework?")
    # by giving the embedding conversational context.
    MEMORY_CONTEXT_WINDOW: int = 10
    # Characters of a retrieved chunk shown as a source excerpt.
    SOURCE_EXCERPT_CHARS: int = 200
    # Sentences the offline responder will quote back.
    OFFLINE_MAX_SENTENCES: int = 4
    # Minimum similarity for an offline-extracted sentence to be included.
    OFFLINE_MIN_SIMILARITY: float = 0.02

    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # -- Resolved, absolute paths -------------------------------------------
    @property
    def backend_dir(self) -> Path:
        """Absolute path to the backend directory."""
        return BACKEND_DIR

    @property
    def chroma_path(self) -> str:
        return resolve_path(self.CHROMA_PERSIST_DIR)

    @property
    def upload_path(self) -> str:
        return resolve_path(self.UPLOAD_DIR)

    @property
    def async_database_url(self) -> str:
        """DATABASE_URL with a sync driver swapped for its async equivalent.

        SQLite paths are rewritten to absolute paths so the engine does not
        depend on the current working directory.
        """
        url = self.DATABASE_URL
        sqlite_prefix = "sqlite:///"
        if url.startswith("sqlite+aiosqlite:///"):
            suffix = url[len("sqlite+aiosqlite:///"):]
            return f"sqlite+aiosqlite:///{resolve_path(suffix)}"
        if url.startswith(sqlite_prefix):
            suffix = url[len(sqlite_prefix):]
            return f"sqlite+aiosqlite:///{resolve_path(suffix)}"
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sqlite_path(self) -> str:
        """Filesystem path of the SQLite file (empty for non-SQLite URLs)."""
        url = self.async_database_url
        prefix = "sqlite+aiosqlite:///"
        if url.startswith(prefix):
            return resolve_path(url[len(prefix):])
        return ""

    @staticmethod
    def _client_kwargs(api_key: str, base_url: str) -> dict:
        """Assemble SDK client arguments for one endpoint.

        `base_url` is omitted entirely when unset rather than passed as an
        empty string. The SDK treats an explicit `base_url=""` as a real
        origin and every request fails with an opaque URL error, so "not
        configured" has to mean "argument absent", not "argument empty".
        """
        kwargs = {"api_key": (api_key or "").strip()}
        url = (base_url or "").strip()
        if url:
            kwargs["base_url"] = url.rstrip("/")
        return kwargs

    @property
    def openai_client_kwargs(self) -> dict:
        """Keyword arguments for the OpenAI-backed clients.

        Used by the embedding client. Chat completions go through
        :meth:`llm_endpoint` instead, because those may be served by Groq.
        """
        return self._client_kwargs(self.OPENAI_API_KEY, self.OPENAI_BASE_URL)

    @property
    def llm_endpoint(self) -> Optional[Tuple[str, dict]]:
        """The API that should answer chat completions, or None to stay offline.

        Returns ``(provider, client_kwargs)``. Groq wins when both keys are
        present: it is the cheaper of the two and the one this project is
        configured against, and silently preferring a pricier key nobody
        remembers adding is the wrong default. ``LLM_PROVIDER`` overrides the
        choice; the forcing and its error messages live in
        ``app.rag.generator.resolve_llm_provider`` rather than here, so that
        this stays a pure description of what is configured.
        """
        if usable_api_key(self.GROQ_API_KEY):
            return "groq", self._client_kwargs(self.GROQ_API_KEY, self.GROQ_BASE_URL)
        if usable_api_key(self.OPENAI_API_KEY):
            return "openai", self._client_kwargs(self.OPENAI_API_KEY, self.OPENAI_BASE_URL)
        return None

    def ensure_directories(self) -> None:
        """Create the runtime data directories."""
        Path(self.chroma_path).mkdir(parents=True, exist_ok=True)
        Path(self.upload_path).mkdir(parents=True, exist_ok=True)
        sqlite_path = self.sqlite_path
        if sqlite_path:
            Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)


settings = Settings()

