"""Document management routes."""

import logging
import os
from typing import List

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_document_service
from app.exceptions import (
    AppError,
    EmptyFileError,
    FileTooLargeError,
    InvalidFileTypeError,
    ProcessingError,
)
from app.models.document import Document
from app.models.schemas import (
    ChunkResponse,
    DeleteResponse,
    DocumentListResponse,
    DocumentResponse,
)
from app.services.document_service import DocumentService
from app.utils.file_handler import ALLOWED_EXTENSIONS, SUPPORTED_TYPES_LABEL

logger = logging.getLogger("rag-chatbot")

router = APIRouter()

#: Browsers and curl disagree on MIME types for .md/.docx, and a mismatched
#: header is not a security signal since the extension allowlist already
#: decides which parser runs. So this is only used to enrich error messages.
_MIME_HINTS = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "application/octet-stream",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def to_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        file_size=document.file_size,
        chunk_count=document.chunk_count,
        status=document.status,
        created_at=document.created_at.isoformat(),
    )


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=201,
    summary="Upload and index a course document",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF, TXT, DOCX, or MD"),
    db: AsyncSession = Depends(get_db),
    service: DocumentService = Depends(get_document_service),
):
    # 1. Validate the extension against the parser allowlist.
    if not file.filename:
        raise InvalidFileTypeError("Uploaded file has no name")

    ext = os.path.splitext(file.filename)[1].lower().lstrip(".")
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidFileTypeError(
            f"'{ext or 'unknown'}' is not supported. "
            f"Allowed types: {SUPPORTED_TYPES_LABEL}",
            details={"allowed": sorted(ALLOWED_EXTENSIONS)},
        )

    if file.content_type and file.content_type not in _MIME_HINTS:
        logger.info(
            "Unexpected MIME type %s for %s; continuing based on extension",
            file.content_type,
            file.filename,
        )

    # 2. Read with a hard size cap so an oversized upload cannot exhaust memory.
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise FileTooLargeError(
            f"File exceeds the {settings.MAX_FILE_SIZE_MB}MB limit",
            details={"max_file_size_mb": settings.MAX_FILE_SIZE_MB},
        )
    if not contents:
        raise EmptyFileError("Uploaded file is empty")

    # 3. Persist the file and create a pending row.
    document = await service.save_document(
        db, filename=file.filename, file_type=ext, file_size=len(contents), contents=contents
    )

    # 4. Parse -> chunk -> embed -> store.
    try:
        await service.process_document(db, document, contents)
    except AppError:
        # Mark the row failed but let the error's own status and code through.
        # Falling through to the handler below would report a 422
        # PROCESSING_ERROR and lose both the cause (the index was built with
        # another provider) and the remedy stated in its message.
        await service.mark_failed(db, document)
        raise
    except Exception as exc:
        logger.exception("Unexpected failure processing %s", document.id)
        await service.mark_failed(db, document)
        raise ProcessingError(
            "Unexpected error while processing the document"
        ) from exc

    await db.refresh(document)
    return to_response(document)


@router.get(
    "/",
    response_model=DocumentListResponse,
    summary="List uploaded documents",
)
async def list_documents(
    db: AsyncSession = Depends(get_db),
    service: DocumentService = Depends(get_document_service),
):
    documents = await service.list_documents(db)
    return DocumentListResponse(
        documents=[to_response(d) for d in documents], total=len(documents)
    )


@router.get(
    "/stats",
    summary="Vector store statistics",
)
async def vector_stats(
    service: DocumentService = Depends(get_document_service),
):
    return await service.embedding_service.get_stats()


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Fetch one document",
)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    service: DocumentService = Depends(get_document_service),
):
    return to_response(await service.get_document(db, document_id))


@router.get(
    "/{document_id}/chunks",
    response_model=List[ChunkResponse],
    summary="Inspect the chunks produced for a document",
)
async def get_document_chunks(
    document_id: str,
    limit: int = Query(10, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    service: DocumentService = Depends(get_document_service),
):
    import json

    # Confirm the document exists so a bad id is a 404, not an empty list.
    await service.get_document(db, document_id)
    chunks = await service.get_chunks(db, document_id, limit=limit)

    return [
        ChunkResponse(
            id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            token_count=chunk.token_count,
            content=chunk.content,
            page_number=(json.loads(chunk.metadata_) or {}).get("page_number")
            if chunk.metadata_
            else None,
        )
        for chunk in chunks
    ]


@router.delete(
    "/{document_id}",
    response_model=DeleteResponse,
    summary="Delete a document and its vectors",
)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    service: DocumentService = Depends(get_document_service),
):
    await service.delete_document(db, document_id)
    return DeleteResponse(status="deleted", id=document_id)
