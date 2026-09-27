"""The RAG pipeline: retrieve, then generate a grounded answer.

Streaming yields :class:`StreamEvent` objects rather than magic strings. The
plan this replaces appended a ``\\n\\n<!--SOURCES:{json}-->`` sentinel to the
answer text and made the route re-parse it; that couples the transport format
to the payload and breaks if the model ever emits the marker itself.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, Sequence

from app.config import settings
from app.rag.generator import NO_CONTEXT_ANSWER, Generated, get_generator
from app.rag.retriever import Retriever

logger = logging.getLogger("rag-chatbot")


@dataclass
class Source:
    document_id: str
    filename: str
    chunk_index: int
    excerpt: str
    similarity: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "chunk_index": self.chunk_index,
            "excerpt": self.excerpt,
            "similarity": self.similarity,
        }


@dataclass
class RAGResult:
    answer: str
    sources: List[Source] = field(default_factory=list)
    mode: str = ""
    used_context: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "sources": [s.to_dict() for s in self.sources],
            "mode": self.mode,
            "used_context": self.used_context,
        }


@dataclass
class StreamEvent:
    """One step of a streamed answer."""

    type: str  # "delta" | "sources"
    text: str = ""
    sources: List[Source] = field(default_factory=list)


class RAGPipeline:
    """Runs retrieval and generation for a single question."""

    def __init__(self, retriever: Optional[Retriever] = None, generator=None):
        self.retriever = retriever or Retriever()
        # Resolved lazily by get_generator() so a provider switch is picked up
        # and so importing this module never needs credentials.
        self._generator = generator

    @property
    def generator(self):
        if self._generator is None:
            self._generator = get_generator()
        return self._generator

    @property
    def mode(self) -> str:
        return self.generator.mode

    async def query(
        self,
        question: str,
        conversation_history: Optional[Sequence[Dict]] = None,
    ) -> RAGResult:
        """Answer `question` from the indexed material."""
        chunks = await self.retriever.retrieve(
            question,
            top_k=settings.TOP_K_RETRIEVAL,
            memory_context=conversation_history,
        )

        if not chunks:
            # Nothing retrieved: answer without calling the model at all, so
            # an empty index can never produce a hallucination.
            return RAGResult(answer=NO_CONTEXT_ANSWER, sources=[], used_context=False)

        # Imported here rather than at module scope to keep the prompt builder
        # in one place.
        from app.rag.generator import build_prompt

        prompt = build_prompt(question, chunks, conversation_history)
        answer = await self.generator.generate(prompt)

        return RAGResult(
            answer=answer,
            sources=self.format_sources(chunks),
            mode=self.generator.mode,
        )

    async def query_stream(
        self,
        question: str,
        conversation_history: Optional[Sequence[Dict]] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Answer `question`, yielding deltas then a final sources event."""
        chunks = await self.retriever.retrieve(
            question,
            top_k=settings.TOP_K_RETRIEVAL,
            memory_context=conversation_history,
        )

        if not chunks:
            yield StreamEvent(type="delta", text=NO_CONTEXT_ANSWER)
            yield StreamEvent(type="sources", sources=[])
            return

        from app.rag.generator import build_prompt

        prompt = build_prompt(question, chunks, conversation_history)

        async for delta in self.generator.generate_stream(prompt):
            if delta:
                yield StreamEvent(type="delta", text=delta)

        yield StreamEvent(type="sources", sources=self.format_sources(chunks))

    def format_sources(self, chunks: Sequence[Dict]) -> List[Source]:
        """Turn retrieved chunks into one source reference per document.

        Only the best-scoring chunk per document is kept: citing a document five
        times is noise, and the top chunk is the one that answered the question.
        """
        limit = settings.SOURCE_EXCERPT_CHARS
        sources: List[Source] = []
        seen: set = set()

        for chunk in chunks:
            metadata = chunk.get("metadata") or {}
            document_id = metadata.get("document_id", "unknown")
            if document_id in seen:
                continue
            seen.add(document_id)

            content = chunk.get("content") or ""
            excerpt = (
                content[:limit] + "..." if len(content) > limit else content
            )
            sources.append(
                Source(
                    document_id=document_id,
                    filename=metadata.get("filename") or "Unknown",
                    chunk_index=int(metadata.get("chunk_index", 0) or 0),
                    excerpt=excerpt,
                    similarity=float(chunk.get("similarity", 0.0) or 0.0),
                )
            )

        return sources


def to_generated(result: RAGResult) -> Generated:
    """Adapter for callers that expect the generator's return type."""
    return Generated(text=result.answer, mode=result.mode)
