"""Embedding generation and vector store operations.

Two providers are supported:

``openai``
    The production path. Batched, cached, and retried. Produces 1536-dim
    vectors for ``text-embedding-3-small``.

``local``
    A dependency-free hashed bag-of-words embedder. It is lexical rather than
    semantic, but it requires no API key and no torch download, so the demo
    still works offline.

Because the two providers emit different vector widths, the provider and
dimension actually used are recorded on the Chroma collection. Any attempt to
query an index built by the other provider is rejected instead of silently
returning garbage.
"""

import hashlib
import inspect
import json
import logging
import math
import os
import re
from collections import Counter, OrderedDict
from typing import Dict, List, Optional, Sequence

from app.config import settings, usable_api_key
from app.exceptions import (
    AppError,
    EmbeddingUnavailableError,
)
from app.exceptions import (
    EmbeddingMismatchError as EmbeddingMismatchErrorBase,
)

logger = logging.getLogger("rag-chatbot")

#: Chroma only accepts str / int / float / bool in metadata.
CHROMA_BATCH_SIZE = 5_000

#: Chroma's wording when a vector's width disagrees with the collection's.
#: Matched on the distinctive fragment so the check survives wording changes in
#: the validation layer (it has moved between releases).
_DIMENSION_MISMATCH = "does not match collection dimensionality"


def _is_dimension_mismatch(exc: BaseException) -> bool:
    """True when `exc` is Chroma rejecting a vector of the wrong width."""
    return _DIMENSION_MISMATCH in str(exc).lower()


# ---------------------------------------------------------------------------
# Local (offline) embedder
# ---------------------------------------------------------------------------


class LocalHashEmbedder:
    """Deterministic hashed term-frequency embedder.

    Unigrams and bigrams are hashed into a fixed-width vector with TF sublinear
    weighting, then L2-normalized so cosine similarity is a plain dot product.

    ``hashlib`` rather than ``hash()`` is deliberate: the built-in hash is
    salted per process, so a salted hash would make the persisted index
    meaningless after a restart.

    Accumulates **unsigned**. Signed hashing is the usual advice, and it was
    tried here, but it has a failure mode that matters more than the collision
    bias it avoids: two features that land in the same bucket with equal counts
    and opposite signs cancel *exactly*, so a word present in a document
    contributes nothing to a query for that word. It is not degraded, it is
    invisible.

    That is not hypothetical. In a 160-feature chunk of a realistic syllabus at
    512 dimensions, 24 buckets collided and 9 cancelled outright -- "homework"
    was annihilated by "trees" landing in the same bucket, and "What does
    homework contribute?" retrieved nothing from the one document that states
    the homework weighting. Widening the vector reduces the rate but never
    removes it: even at 8192 dimensions a term in this corpus still cancelled.

    Unsigned accumulation makes presence sufficient. If `t` occurs in the
    document, its bucket holds a strictly positive weight, so the dot product
    with the single-feature query vector for `t` is positive by construction --
    collisions can only add to a match, never erase one. The cost is that
    unrelated documents share some mass through collisions, which is why
    retrieval here is a high-recall lexical net and precision is applied later,
    by scoring individual sentences against the question.
    """

    def __init__(self, dim: int = 2048):
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim
        self._cache: "OrderedDict[str, List[float]]" = OrderedDict()
        self._cache_size = settings.EMBEDDING_CACHE_SIZE

    @property
    def model_name(self) -> str:
        return f"local-hash-{self.dim}"

    @property
    def dimension(self) -> int:
        return self.dim

    def _features(self, text: str) -> Counter:
        words = re.findall(r"[a-z0-9]+", text.lower())
        features = Counter(words)
        # Bigrams add a little word-order sensitivity at negligible cost.
        for i in range(len(words) - 1):
            features[f"{words[i]}_{words[i + 1]}"] += 1
        return features

    def embed(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * self.dim

        cached = self._cache.get(text)
        if cached is not None:
            self._cache.move_to_end(text)
            return cached

        vector = [0.0] * self.dim
        for term, count in self._features(text).items():
            digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            vector[index] += 1.0 + math.log(count)

        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]

        self._cache[text] = vector
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return vector

    def embed_many(self, texts: Sequence[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------


class OpenAIEmbedder:
    """Thin async wrapper over the OpenAI embeddings endpoint."""

    def __init__(self):
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=2,
            **settings.openai_client_kwargs,
        )
        self._cache: "OrderedDict[str, List[float]]" = OrderedDict()
        self._cache_size = settings.EMBEDDING_CACHE_SIZE

    @property
    def model_name(self) -> str:
        return settings.OPENAI_EMBEDDING_MODEL

    @property
    def dimension(self) -> int:
        return 1536

    async def embed_many(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)
        pending: List[int] = []

        for i, text in enumerate(texts):
            cached = self._cache.get(text)
            if cached is not None:
                self._cache.move_to_end(text)
                results[i] = cached
            else:
                pending.append(i)

        batch_size = max(1, settings.EMBEDDING_BATCH_SIZE)
        for start in range(0, len(pending), batch_size):
            window = pending[start : start + batch_size]
            batch = [texts[i] for i in window]

            response = await self._client.embeddings.create(
                model=self.model_name, input=batch
            )
            # The API does not guarantee response order matches input order.
            by_index = {item.index: item.embedding for item in response.data}
            for offset, original_index in enumerate(window):
                vector = by_index.get(offset)
                if vector is None:
                    raise RuntimeError(
                        f"Embedding response missing index {offset} for batch "
                        f"starting at {start}"
                    )
                results[original_index] = vector
                self._remember(texts[original_index], vector)

        return [r if r is not None else [] for r in results]

    def _remember(self, text: str, vector: List[float]) -> None:
        self._cache[text] = vector
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------


def _has_usable_openai_key() -> bool:
    return usable_api_key(settings.OPENAI_API_KEY)


def resolve_provider() -> str:
    """Return the provider to use: 'openai' or 'local'."""
    requested = (settings.EMBEDDING_PROVIDER or "auto").strip().lower()
    if requested == "openai":
        if not _has_usable_openai_key():
            raise RuntimeError(
                "EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is missing or is "
                "still the .env.example placeholder"
            )
        return "openai"
    if requested == "local":
        return "local"
    return "openai" if _has_usable_openai_key() else "local"


def active_model_name(provider: str) -> str:
    if provider == "openai":
        return settings.OPENAI_EMBEDDING_MODEL
    return f"local-hash-{settings.LOCAL_EMBEDDING_DIM}"


# ---------------------------------------------------------------------------
# Vector store
# ---------------------------------------------------------------------------


class EmbeddingMismatchError(EmbeddingMismatchErrorBase):
    """Re-exported here so the vector store's contract stays in one place.

    Defined in :mod:`app.exceptions` to carry an HTTP mapping; imported by this
    module's callers as ``from app.services.embedding_service import
    EmbeddingMismatchError``.
    """


class EmbeddingService:
    """Generates embeddings and persists/searches them in Chroma."""

    _client = None
    _collection = None
    _embedder = None
    _provider: Optional[str] = None

    # -- Chroma ----------------------------------------------------------

    @classmethod
    def get_client(cls):
        if cls._client is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            cls._client = chromadb.PersistentClient(
                path=settings.chroma_path,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return cls._client

    @classmethod
    def get_collection(cls):
        if cls._collection is None:
            client = cls.get_client()
            cls._collection = client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return cls._collection

    @classmethod
    def _recreate_collection(cls):
        """Drop the collection and make a new empty one of the current width.

        Chroma fixes a collection's dimensionality at creation and keeps it in
        its own ``collections`` table with no public accessor, so an index
        cannot be re-widened in place -- the only way through is a fresh
        collection. That is safe to do here because the caller has already
        established the collection holds nothing.
        """
        client = cls.get_client()
        try:
            client.delete_collection(settings.CHROMA_COLLECTION_NAME)
        except Exception:  # noqa: BLE001 - best effort; recreated either way
            logger.debug(
                "delete_collection(%s) failed; recreating anyway",
                settings.CHROMA_COLLECTION_NAME,
                exc_info=True,
            )
        cls._collection = client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Recreated collection at width %d", cls.get_embedder().dimension)
        return cls._collection

    # -- Embedder --------------------------------------------------------

    @classmethod
    def get_embedder(cls):
        if cls._embedder is None:
            provider = resolve_provider()
            if provider == "openai":
                cls._embedder = OpenAIEmbedder()
            else:
                cls._embedder = LocalHashEmbedder(dim=settings.LOCAL_EMBEDDING_DIM)
            cls._provider = provider
            logger.info("Embedding provider: %s", cls._embedder.model_name)
        return cls._embedder

    @classmethod
    def get_provider(cls) -> str:
        if cls._provider is None:
            cls.get_embedder()
        return cls._provider or "local"

    @classmethod
    def reset(cls) -> None:
        """Drop cached clients. Used by tests and by document re-indexing."""
        cls._client = None
        cls._collection = None
        cls._embedder = None
        cls._provider = None

    # -- Index metadata --------------------------------------------------
    #
    # Chroma cannot update collection metadata in place: `modify()` raises
    # whenever the payload contains `hnsw:space`, and that key must always be
    # present to keep the collection on cosine distance. Bookkeeping therefore
    # lives in a small JSON sidecar next to the Chroma directory.

    @staticmethod
    def _index_info_path() -> str:
        return os.path.join(settings.chroma_path, "index_info.json")

    @classmethod
    def _read_index_info(cls) -> Dict[str, object]:
        path = cls._index_info_path()
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            logger.warning("Could not read index info at %s", path, exc_info=True)
            return {}

    @classmethod
    def _write_index_info(cls, provider: str, model: str, dimension: int) -> None:
        path = cls._index_info_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "embedding_provider": provider,
                        "embedding_model": model,
                        "embedding_dimension": int(dimension),
                    },
                    handle,
                    indent=2,
                )
        except OSError:
            logger.warning("Could not persist index info to %s", path, exc_info=True)

    @classmethod
    def _record_index_info(cls, provider: str, model: str, dimension: int) -> None:
        cls._write_index_info(provider, model, dimension)

    @classmethod
    def _clear_index_info(cls) -> None:
        """Forget which model the index was built with.

        Only safe once the collection is known to be empty; a mismatch against a
        populated index is a real constraint and must keep failing.
        """
        try:
            os.remove(cls._index_info_path())
        except FileNotFoundError:
            pass
        except OSError:
            logger.warning(
                "Could not clear stale index info at %s", cls._index_info_path(), exc_info=True
            )

    @classmethod
    def _assert_compatible(cls, provider: str, model: str) -> None:
        """Refuse to mix providers against an existing index.

        An empty index is compatible with every provider, so it is never a
        mismatch. The recorded model is stale bookkeeping, not a constraint:
        keeping it would deadlock the obvious recovery. Changing
        ``LOCAL_EMBEDDING_DIM`` or adding a real OpenAI key leaves the old
        model in the sidecar, and the documented remedy is "delete the documents
        and upload them again" -- but if deleting the last document still
        reported a mismatch, that remedy could never succeed and the index would
        be permanently stuck on the old model. The sidecar is dropped here so
        the next ``store_embeddings`` records the current one.
        """
        info = cls._read_index_info()
        stored = info.get("embedding_model")
        if not stored or stored == model:
            return

        if cls.get_collection().count() == 0:
            logger.info(
                "Index is empty; discarding stale index info %r in favour of %r",
                stored,
                model,
            )
            cls._clear_index_info()
            return

        raise EmbeddingMismatchError(
            f"The vector index was built with '{stored}' but the current "
            f"provider produces '{model}'. Re-index your documents (delete "
            f"and upload them again) or change EMBEDDING_PROVIDER."
        )

    # -- Embedding -------------------------------------------------------

    async def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        """Embed a batch of texts, reusing cached vectors where possible.

        Providers may be sync (local, CPU-bound) or async (OpenAI, network);
        the result is awaited only when it is actually awaitable.

        A provider failure (bad key, network down, rate limit) is reported as
        ``EmbeddingUnavailableError`` so callers get a 503 with a usable message
        instead of an opaque 500. Callers that already wrap this -- the upload
        path reports a per-document failure -- keep that behaviour.
        """
        texts = list(texts)
        if not texts:
            return []
        embedder = self.get_embedder()
        # Checked before embedding so a mismatched provider fails immediately
        # rather than after a pointless round trip.
        self._assert_compatible(self.get_provider(), embedder.model_name)

        try:
            vectors = embedder.embed_many(texts)
            if inspect.isawaitable(vectors):
                vectors = await vectors
        except EmbeddingMismatchError:
            raise
        except AppError:
            raise
        except Exception as exc:
            logger.warning("Embedding provider %s failed: %s", self.get_provider(), exc)
            raise EmbeddingUnavailableError(
                f"The embedding service could not be reached: {exc}"
            ) from exc
        return vectors

    async def embed_query(self, text: str) -> List[float]:
        vectors = await self.embed_texts([text])
        return vectors[0]

    # -- Write -----------------------------------------------------------

    async def store_embeddings(
        self,
        document_id: str,
        chunks: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        filename: str = "",
    ) -> None:
        """Upsert chunk vectors with source metadata for citations."""
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Got {len(chunks)} chunks but {len(embeddings)} embeddings"
            )
        if not chunks:
            return

        collection = self.get_collection()
        embedder = self.get_embedder()
        self._assert_compatible(self.get_provider(), embedder.model_name)
        self._record_index_info(self.get_provider(), embedder.model_name, embedder.dimension)

        try:
            self._upsert_batches(collection, document_id, chunks, embeddings, filename)
        except Exception as exc:
            if not _is_dimension_mismatch(exc) or collection.count() > 0:
                raise
            # An *empty* index whose width predates the current provider. The
            # sidecar check above already cleared the bookkeeping, but a Chroma
            # collection keeps its width in its own metadata and cannot be
            # re-widened, so the collection itself has to be rebuilt. Nothing is
            # lost -- it is empty -- and this is the only route that lets the
            # documented "delete the documents and upload them again" remedy
            # actually complete.
            logger.info(
                "Empty index has a stale width (%s); rebuilding it", exc
            )
            collection = self._recreate_collection()
            self._upsert_batches(collection, document_id, chunks, embeddings, filename)

        logger.info("Stored %s chunks for document %s", len(chunks), document_id)

    @staticmethod
    def _upsert_batches(
        collection,
        document_id: str,
        chunks: Sequence[str],
        embeddings: Sequence[Sequence[float]],
        filename: str,
    ) -> None:
        for start in range(0, len(chunks), CHROMA_BATCH_SIZE):
            stop = min(start + CHROMA_BATCH_SIZE, len(chunks))
            collection.upsert(
                ids=[f"{document_id}::chunk_{i}" for i in range(start, stop)],
                embeddings=[list(v) for v in embeddings[start:stop]],
                documents=list(chunks[start:stop]),
                metadatas=[
                    {
                        "document_id": document_id,
                        "filename": filename,
                        "chunk_index": i,
                    }
                    for i in range(start, stop)
                ],
            )

    async def delete_by_document_id(self, document_id: str) -> None:
        """Remove every vector belonging to a document."""
        self.get_collection().delete(where={"document_id": document_id})

    # -- Read ------------------------------------------------------------

    async def search(
        self,
        query_embedding: Sequence[float],
        top_k: Optional[int] = None,
    ) -> List[dict]:
        """Return the nearest chunks, best first.

        Each result is ``{content, metadata, distance, similarity}``. Chunks
        farther than ``MAX_RETRIEVAL_DISTANCE`` are dropped so clearly
        unrelated questions do not drag in noise.
        """
        top_k = top_k or settings.TOP_K_RETRIEVAL
        collection = self.get_collection()

        if collection.count() == 0:
            return []

        raw = collection.query(
            query_embeddings=[list(query_embedding)],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        documents = (raw.get("documents") or [[]])[0]
        metadatas = (raw.get("metadatas") or [[]])[0]
        distances = (raw.get("distances") or [[]])[0]

        results: List[dict] = []
        for i, content in enumerate(documents):
            distance = float(distances[i]) if i < len(distances) else 1.0
            if distance > settings.MAX_RETRIEVAL_DISTANCE:
                continue
            results.append(
                {
                    "content": content,
                    "metadata": dict(metadatas[i]) if i < len(metadatas) and metadatas[i] else {},
                    "distance": distance,
                    "similarity": round(1.0 - distance, 4),
                }
            )
        return results

    async def search_by_text(self, query: str, top_k: Optional[int] = None) -> List[dict]:
        """Embed `query` then search. Convenience for tests and debugging."""
        return await self.search(await self.embed_query(query), top_k)

    # -- Introspection ---------------------------------------------------

    async def get_stats(self) -> dict:
        collection = self.get_collection()
        info = self._read_index_info()
        return {
            "collection_name": settings.CHROMA_COLLECTION_NAME,
            "total_chunks": collection.count(),
            "embedding_provider": self.get_provider(),
            "embedding_model": active_model_name(self.get_provider()),
            "indexed_with": info.get("embedding_model"),
        }


_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Return the shared EmbeddingService instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def get_chroma_client():
    """Return the shared persistent Chroma client."""
    return EmbeddingService.get_client()


def get_chroma_collection():
    """Return the shared collection of course document chunks."""
    return EmbeddingService.get_collection()
