"""Context retrieval for the RAG pipeline."""

import logging
from typing import Dict, List, Optional

from app.config import settings
from app.services.embedding_service import get_embedding_service

logger = logging.getLogger("rag-chatbot")


class Retriever:
    """Finds the chunks most relevant to a question."""

    def __init__(self, embedding_service=None):
        # Injected rather than constructed: the embedding service caches a
        # Chroma client and a provider, and building a second one per request
        # would open a second connection to the same store.
        self.embedding_service = embedding_service or get_embedding_service()

    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        memory_context: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """Return the chunks most relevant to `query`, best first.

        When `memory_context` is provided (a list of ``{"role": ..., "content": ...}``
        dicts in chronological order), the most recent messages are prepended to
        the query to form an augmented search string. This resolves follow-up
        questions that depend on prior conversation (e.g. "What about homework?"
        after a discussion of assignments).

        Returns an empty list when the index has no documents at all, which is
        the "nothing to answer from" case the pipeline turns into a fallback
        message.
        """
        query = (query or "").strip()
        if not query:
            return []

        top_k = top_k or settings.TOP_K_RETRIEVAL

        augmented_query = self._augment_query(query, memory_context)
        query_embedding = await self.embedding_service.embed_query(augmented_query)
        results = await self.embedding_service.search(query_embedding, top_k)

        logger.debug("Retrieved %d chunks for %r", len(results), query[:60])
        return results

    def _augment_query(
        self, query: str, memory_context: Optional[List[Dict]] = None
    ) -> str:
        """Prepend recent memory messages to `query` for retrieval.

        Only the last ``MEMORY_CONTEXT_WINDOW`` messages are used, and only
        their text content (not role labels) is included. The result is a
        single string that captures both the conversational context and the
        current question.
        """
        if not memory_context:
            return query

        window = memory_context[-settings.MEMORY_CONTEXT_WINDOW :]
        context_parts = [
            m.get("content", "").strip()
            for m in window
            if m.get("content", "").strip()
        ]

        if not context_parts:
            return query

        context_text = " ".join(context_parts)
        return f"{context_text} {query}".strip()
