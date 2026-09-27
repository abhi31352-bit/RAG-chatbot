"""Document ingestion: store the file, then index it.

Pipeline for one upload: save file -> parse text -> chunk -> embed -> persist
chunk rows in SQLite and vectors in Chroma.
"""

import json
import logging
import os
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions import (
    AppError,
    DocumentNotFoundError,
    ProcessingError,
)
from app.models.document import Chunk, Document, generate_id
from app.services.embedding_service import get_embedding_service
from app.utils.file_handler import (
    DocumentParseError,
    FileHandler,
    UnsupportedFileTypeError,
    get_file_handler,
)
from app.utils.text_processor import (
    InvalidChunkConfigError,
    TextProcessor,
    get_text_processor,
)

logger = logging.getLogger("rag-chatbot")

#: Terminal and in-flight document states.
STATUS_PENDING = "pending"
STATUS_PROCESSED = "processed"
STATUS_FAILED = "failed"


class DocumentService:
    """Coordinates parsing, chunking, embedding, and persistence."""

    def __init__(
        self,
        file_handler: Optional[FileHandler] = None,
        text_processor: Optional[TextProcessor] = None,
    ):
        self.file_handler = file_handler or get_file_handler()
        self.text_processor = text_processor or get_text_processor()
        self.embedding_service = get_embedding_service()
        self.upload_dir = settings.upload_path
        os.makedirs(self.upload_dir, exist_ok=True)

    # -- Storage ---------------------------------------------------------

    def _safe_upload_path(self, document_id: str, filename: str) -> str:
        """Build an on-disk path that cannot escape the upload directory.

        The user-supplied name is sanitized and prefixed with the document id
        rather than trusted directly.
        """
        ext = os.path.splitext(filename)[1].lower()
        base = os.path.basename(filename) or "upload"
        # Strip path separators and anything that is not filename-safe.
        base = "".join(c for c in base if c.isalnum() or c in "._- ").strip() or "upload"
        return os.path.join(self.upload_dir, f"{document_id}_{base}{ext if not base.endswith(ext) else ''}")

    async def save_document(
        self,
        db: AsyncSession,
        filename: str,
        file_type: str,
        file_size: int,
        contents: bytes,
    ) -> Document:
        """Write the file to disk and create its (pending) database row."""
        document_id = generate_id("doc")
        file_path = self._safe_upload_path(document_id, filename)

        try:
            with open(file_path, "wb") as handle:
                handle.write(contents)
        except OSError as exc:
            raise ProcessingError(f"Could not save uploaded file: {exc}") from exc

        document = Document(
            id=document_id,
            filename=os.path.basename(filename),
            file_type=file_type.lstrip(".").lower(),
            file_size=file_size,
            file_path=file_path,
            status=STATUS_PENDING,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document

    # -- Processing ------------------------------------------------------

    async def process_document(
        self,
        db: AsyncSession,
        document: Document,
        contents: bytes,
    ) -> int:
        """Parse, chunk, embed, and persist `document`. Returns the chunk count.

        On failure the document is left in the caller's session with status
        'failed'; the caller is responsible for committing that.
        """
        # 1. Parse
        try:
            text, page_boundaries = self.file_handler.parse_with_pages(
                contents, document.file_type
            )
        except (UnsupportedFileTypeError, DocumentParseError) as exc:
            raise ProcessingError(str(exc)) from exc

        if not text or not text.strip():
            raise ProcessingError(
                "No text could be extracted. Scanned or image-only PDFs require "
                "OCR, which is not enabled."
            )

        # 2. Chunk (keeping spans so each chunk can be traced to its page)
        try:
            spans = self.text_processor.chunk_text_with_spans(
                text,
                chunk_size=settings.CHUNK_SIZE,
                overlap=settings.CHUNK_OVERLAP,
            )
        except InvalidChunkConfigError as exc:
            raise ProcessingError(f"Chunking failed: {exc}") from exc

        if not spans:
            raise ProcessingError("Document produced no usable text chunks")

        chunks = [chunk for chunk, _, _ in spans]

        # 3. Embed
        try:
            embeddings = await self.embedding_service.embed_texts(chunks)
        except AppError:
            # Carries its own status and code. Re-wrapping would turn a 409
            # EMBEDDING_MISMATCH (index built with another provider) or a 503
            # EMBEDDING_UNAVAILABLE into a generic 422 PROCESSING_ERROR, hiding
            # both the cause and the remedy from the client.
            raise
        except Exception as exc:
            raise ProcessingError(
                f"Could not generate embeddings: {exc}"
            ) from exc

        # 4. Persist vectors + chunk rows
        try:
            await self.embedding_service.store_embeddings(
                document_id=document.id,
                chunks=chunks,
                embeddings=embeddings,
                filename=document.filename,
            )
        except AppError:
            raise
        except Exception as exc:
            raise ProcessingError(f"Could not store embeddings: {exc}") from exc

        await self.replace_chunks(db, document.id, spans, page_boundaries)

        document.chunk_count = len(chunks)
        document.status = STATUS_PROCESSED
        await db.commit()
        return len(chunks)

    async def replace_chunks(
        self,
        db: AsyncSession,
        document_id: str,
        spans: Sequence[Tuple[str, int, int]],
        page_boundaries: Optional[Sequence[Tuple[int, int]]] = None,
    ) -> None:
        """Replace the stored chunk rows for a document.

        Chunk rows are the source of truth for source excerpts shown in chat
        citations, so they are written alongside the vectors.

        `spans` are ``(content, start_char, end_char)`` triples and
        `page_boundaries` are ``(page_number, char_offset)`` pairs; the latter
        comes from PDF parsing and is empty for other formats.
        """
        await db.execute(delete(Chunk).where(Chunk.document_id == document_id))

        for index, (content, start_char, _end_char) in enumerate(spans):
            page_number = page_for_offset(start_char, page_boundaries)
            metadata: dict = {"chunk_index": index}
            if page_number is not None:
                metadata["page_number"] = page_number

            db.add(
                Chunk(
                    id=f"{document_id}::chunk_{index}",
                    document_id=document_id,
                    content=content,
                    chunk_index=index,
                    token_count=self.text_processor.count_tokens(content),
                    metadata_=json.dumps(metadata),
                )
            )
        await db.flush()

    # -- Reads -----------------------------------------------------------

    async def get_document(self, db: AsyncSession, document_id: str) -> Document:
        result = await db.execute(
            select(Document).where(Document.id == document_id)
        )
        document = result.scalar_one_or_none()
        if document is None:
            raise DocumentNotFoundError(details={"document_id": document_id})
        return document

    async def list_documents(self, db: AsyncSession) -> List[Document]:
        result = await db.execute(
            select(Document).order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_chunks(
        self, db: AsyncSession, document_id: str, limit: Optional[int] = None
    ) -> List[Chunk]:
        stmt = (
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
        if limit:
            stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # -- Deletion --------------------------------------------------------

    async def delete_document(self, db: AsyncSession, document_id: str) -> Document:
        """Delete a document, its vectors, its chunk rows, and its file."""
        document = await self.get_document(db, document_id)

        # Vectors first: a stale vector index is harder to notice than a
        # leftover file, and this is the failure users would actually hit.
        try:
            await self.embedding_service.delete_by_document_id(document_id)
        except Exception:
            logger.exception(
                "Failed to remove vectors for document %s; "
                "the document will still be deleted",
                document_id,
            )

        await db.delete(document)
        await db.commit()

        try:
            if document.file_path and os.path.exists(document.file_path):
                os.remove(document.file_path)
        except OSError:
            logger.exception("Could not remove file for document %s", document_id)

        return document

    async def mark_failed(self, db: AsyncSession, document: Document) -> None:
        document.status = STATUS_FAILED
        await db.commit()


def page_for_offset(
    char_offset: int, page_boundaries: Optional[Sequence[Tuple[int, int]]]
) -> Optional[int]:
    """Map a character offset in the parsed text to a 1-based PDF page.

    `page_boundaries` is a list of ``(page_number, char_offset)`` pairs sorted
    by offset, as produced by :meth:`FileHandler.parse_with_pages`. The page of
    a chunk is the last page whose start offset is <= the chunk's start.
    Returns None when the format has no pages.
    """
    if not page_boundaries:
        return None
    page = None
    for page_number, start in page_boundaries:
        if start <= char_offset:
            page = page_number
        else:
            break
    return page


_document_service: Optional[DocumentService] = None


def get_document_service() -> DocumentService:
    """Return the shared DocumentService instance."""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service
