"""Tests for the document upload / list / chunk / delete endpoints."""

import io
import os

import pytest

from app.services.embedding_service import get_chroma_collection

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _empty_database(clean_db):
    """Each test starts with no documents so list/count assertions are exact."""
    yield

SYLLABUS = (
    "CS 401 Machine Learning - Course Syllabus\n\n"
    "Instructor: Dr. Ada Lovelace. Office hours Tuesdays 2-4pm.\n\n"
    "Grading: the final examination is worth forty percent of the course grade. "
    "Homework is thirty percent and the term project is thirty percent.\n\n"
    "Late submissions lose ten percent of the mark per day.\n"
)


def make_docx_bytes(paragraphs) -> bytes:
    import docx

    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


async def upload(client, name, content, content_type="text/plain"):
    return await client.post(
        "/api/documents/upload",
        files={"file": (name, content, content_type)},
    )


# -- Upload: happy paths ---------------------------------------------------


async def test_upload_text_file(client):
    response = await upload(client, "syllabus.txt", SYLLABUS.encode())
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["filename"] == "syllabus.txt"
    assert body["file_type"] == "txt"
    assert body["file_size"] == len(SYLLABUS.encode())
    assert body["status"] == "processed"
    assert body["chunk_count"] >= 1
    assert body["id"].startswith("doc_")
    assert body["created_at"]


async def test_upload_markdown_file(client):
    response = await upload(client, "notes.md", b"# Week 1\n\nIntro to ML", "text/markdown")
    assert response.status_code == 201
    assert response.json()["file_type"] == "md"


async def test_upload_docx_file(client):
    payload = make_docx_bytes(["Lecture one", "Lecture two"])
    response = await upload(
        client,
        "slides.docx",
        payload,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert response.status_code == 201
    assert response.json()["file_type"] == "docx"


async def test_upload_persists_file_on_disk(client):
    from app.config import settings

    response = await upload(client, "persisted.txt", b"some searchable course content")
    assert response.status_code == 201
    assert os.listdir(settings.upload_path), "uploaded file should be written to disk"


async def test_upload_indexes_vectors(client):
    before = get_chroma_collection().count()
    await upload(client, "indexed.txt", SYLLABUS.encode())
    assert get_chroma_collection().count() > before


async def test_upload_persists_chunk_rows(client):
    response = await upload(client, "chunks.txt", SYLLABUS.encode())
    chunks = await client.get(f"/api/documents/{response.json()['id']}/chunks")
    assert chunks.status_code == 200
    body = chunks.json()
    assert len(body) == response.json()["chunk_count"]
    assert body[0]["content"]
    assert body[0]["token_count"] > 0
    assert body[0]["chunk_index"] == 0


async def test_upload_same_name_twice_creates_two_documents(client):
    first = await upload(client, "dup.txt", b"first body about regression models")
    second = await upload(client, "dup.txt", b"second body about clustering models")
    assert first.json()["id"] != second.json()["id"]


# -- Upload: rejections ----------------------------------------------------


async def test_reject_unsupported_extension(client):
    response = await upload(client, "malware.exe", b"MZ binary junk", "application/octet-stream")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILE_TYPE"


async def test_reject_extensionless_file(client):
    response = await upload(client, "noextension", b"plain text", "text/plain")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_FILE_TYPE"


async def test_reject_empty_file(client):
    response = await upload(client, "empty.txt", b"", "text/plain")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "EMPTY_FILE"


async def test_reject_oversized_file(client, monkeypatch):
    monkeypatch.setattr("app.routes.documents.settings.MAX_FILE_SIZE_MB", 0)
    response = await upload(client, "big.txt", b"x" * 1024, "text/plain")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


async def test_reject_unparseable_pdf(client):
    response = await upload(client, "broken.pdf", b"this is not a pdf", "application/pdf")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PROCESSING_ERROR"


async def test_reject_pdf_with_no_extractable_text(client):
    """A scanned PDF parses fine but yields nothing to index."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)

    response = await upload(client, "scanned.pdf", buffer.getvalue(), "application/pdf")
    assert response.status_code == 422
    assert "OCR" in response.json()["error"]["message"]


async def test_failed_upload_is_recorded_as_failed(client):
    response = await upload(client, "broken.pdf", b"definitely not a pdf", "application/pdf")
    assert response.status_code == 422

    documents = (await client.get("/api/documents/")).json()["documents"]
    failed = [d for d in documents if d["filename"] == "broken.pdf"]
    assert failed and failed[0]["status"] == "failed"
    assert failed[0]["chunk_count"] == 0


async def test_upload_reports_provider_mismatch_with_its_own_code(client):
    """A mismatched index must not be laundered into a generic 422.

    Changing the embedding provider and re-uploading used to come back as
    PROCESSING_ERROR "Unexpected error while processing the document", which
    hid both the cause and the remedy. Each layer that catches a broad
    exception has to let AppError through with its own status and code.
    """
    from app.services import embedding_service as es

    # Populate so the index is genuinely dimension-locked.
    await upload(client, "first.txt", SYLLABUS.encode())
    es.EmbeddingService._write_index_info("openai", "text-embedding-3-small", 1536)

    response = await upload(client, "second.txt", b"more course content about regression")

    assert response.status_code == 409, response.text
    error = response.json()["error"]
    assert error["code"] == "EMBEDDING_MISMATCH"
    # The message has to keep naming the remedy, not just the failure.
    assert "Re-index" in error["message"]


async def test_upload_marks_the_document_failed_on_provider_mismatch(client):
    """A mismatched upload must not leave a row stuck in 'pending'."""
    from app.services import embedding_service as es

    await upload(client, "locked.txt", SYLLABUS.encode())
    es.EmbeddingService._write_index_info("openai", "text-embedding-3-small", 1536)

    await upload(client, "rejected.txt", b"content that cannot be embedded")

    documents = (await client.get("/api/documents/")).json()["documents"]
    rejected = [d for d in documents if d["filename"] == "rejected.txt"]
    assert rejected and rejected[0]["status"] == "failed"


# -- Listing ---------------------------------------------------------------


async def test_list_documents_empty(client):
    body = (await client.get("/api/documents/")).json()
    assert body == {"documents": [], "total": 0}


async def test_list_documents_newest_first(client):
    first = await upload(client, "a.txt", b"alpha content about neural networks")
    second = await upload(client, "b.txt", b"beta content about database indexes")
    body = (await client.get("/api/documents/")).json()

    assert body["total"] == 2
    assert body["documents"][0]["id"] == second.json()["id"]
    assert first.json()["id"] in [d["id"] for d in body["documents"]]


async def test_get_single_document(client):
    created = (await upload(client, "single.txt", b"content for one document")).json()
    response = await client.get(f"/api/documents/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_unknown_document_is_404(client):
    response = await client.get("/api/documents/doc_does_not_exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


# -- Chunks ----------------------------------------------------------------


async def test_page_for_offset_maps_chars_to_pages():
    from app.services.document_service import page_for_offset

    # Pages 1-4 start at char offsets 0, 100, 200, 300.
    boundaries = [(1, 0), (2, 100), (3, 200), (4, 300)]
    assert page_for_offset(0, boundaries) == 1
    assert page_for_offset(99, boundaries) == 1
    assert page_for_offset(100, boundaries) == 2
    assert page_for_offset(250, boundaries) == 3
    assert page_for_offset(9999, boundaries) == 4
    assert page_for_offset(50, []) is None
    assert page_for_offset(50, None) is None


async def test_page_boundaries_skip_blank_pages():
    """A blank page contributes no text, so the next real page keeps its number."""
    from app.services.document_service import page_for_offset

    # Page 2 was blank and omitted; page 3 starts at offset 150.
    boundaries = [(1, 0), (3, 150)]
    assert page_for_offset(0, boundaries) == 1
    assert page_for_offset(160, boundaries) == 3


async def test_chunks_for_unknown_document_is_404(client):
    response = await client.get("/api/documents/doc_nope/chunks")
    assert response.status_code == 404


async def test_chunks_limit_is_respected(client):
    created = (await upload(client, "many.txt", ("sentence about grading. " * 400).encode())).json()
    body = (await client.get(f"/api/documents/{created['id']}/chunks?limit=3")).json()
    assert len(body) == 3


async def test_pdf_pages_are_attributed_to_chunks(client, monkeypatch):
    """Chunks spanning a multi-page PDF must record the page they start on.

    Authoring a real multi-page PDF in a test is impractical, so the parser is
    stubbed to return known text plus known page boundaries; everything
    downstream (chunking, span mapping, persistence) is the real code.
    """
    pages = [
        "PAGE-ONE " + "alpha content about regression. " * 60,
        "PAGE-TWO " + "beta content about clustering. " * 60,
        "PAGE-THREE " + "gamma content about decision trees. " * 60,
    ]
    text = "\n\n".join(pages)
    boundaries = []
    cursor = 0
    for number, page in enumerate(pages, start=1):
        boundaries.append((number, cursor))
        cursor += len(page) + 2

    from app.services.document_service import get_document_service

    monkeypatch.setattr(
        get_document_service().file_handler,
        "parse_with_pages",
        lambda contents, file_type: (text, boundaries),
    )

    response = await upload(client, "paged.txt", b"placeholder")
    assert response.status_code == 201
    chunks = (await client.get(f"/api/documents/{response.json()['id']}/chunks?limit=50")).json()

    assert len(chunks) >= 3
    pages_seen = {c["page_number"] for c in chunks}
    assert pages_seen == {1, 2, 3}, f"expected all three pages, got {pages_seen}"

    # Page numbers must be non-decreasing as the chunks progress.
    numbers = [c["page_number"] for c in chunks]
    assert numbers == sorted(numbers)
    assert numbers[0] == 1
    assert numbers[-1] == 3


async def test_non_pdf_chunks_have_no_page_number(client):
    created = (await upload(client, "nopages.txt", ("plain course content. " * 300).encode())).json()
    chunks = (await client.get(f"/api/documents/{created['id']}/chunks?limit=50")).json()
    assert len(chunks) >= 2, "need a multi-chunk document for this to mean anything"
    assert all(c["page_number"] is None for c in chunks)


async def test_chunks_limit_validation(client):
    created = (await upload(client, "valid.txt", b"content here for validation")).json()
    assert (await client.get(f"/api/documents/{created['id']}/chunks?limit=0")).status_code == 422
    assert (await client.get(f"/api/documents/{created['id']}/chunks?limit=999")).status_code == 422


# -- Deletion --------------------------------------------------------------


async def test_delete_document(client):
    created = (await upload(client, "delete-me.txt", b"content scheduled for deletion")).json()
    response = await client.delete(f"/api/documents/{created['id']}")
    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "id": created["id"]}
    assert (await client.get(f"/api/documents/{created['id']}")).status_code == 404


async def test_delete_removes_vectors(client):
    before = get_chroma_collection().count()
    created = (await upload(client, "vectorful.txt", b"vectors that must disappear")).json()
    assert get_chroma_collection().count() > before

    await client.delete(f"/api/documents/{created['id']}")
    remaining = get_chroma_collection().get(where={"document_id": created["id"]})
    assert remaining["ids"] == []


async def test_delete_removes_chunk_rows(client):
    created = (await upload(client, "chunky.txt", b"chunk rows that must cascade away")).json()
    await client.delete(f"/api/documents/{created['id']}")

    from sqlalchemy import select

    from app.models.database import async_session
    from app.models.document import Chunk

    async with async_session() as session:
        rows = await session.execute(
            select(Chunk).where(Chunk.document_id == created["id"])
        )
        assert rows.scalars().all() == []


async def test_delete_removes_file_from_disk(client):
    from app.config import settings

    created = (await upload(client, "ondisk.txt", b"file bytes to clean up")).json()
    await client.delete(f"/api/documents/{created['id']}")
    remaining = [n for n in os.listdir(settings.upload_path) if created["id"] in n]
    assert remaining == []


async def test_delete_unknown_document_is_404(client):
    response = await client.delete("/api/documents/doc_missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


async def test_delete_preserves_other_documents(client):
    keep = (await upload(client, "keep.txt", b"this document must survive deletion")).json()
    drop = (await upload(client, "drop.txt", b"this document will be deleted now")).json()

    await client.delete(f"/api/documents/{drop['id']}")
    assert (await client.get(f"/api/documents/{keep['id']}")).status_code == 200


# -- Stats -----------------------------------------------------------------


async def test_stats_reports_chunks(client):
    await upload(client, "stats.txt", SYLLABUS.encode())
    body = (await client.get("/api/documents/stats")).json()
    assert body["total_chunks"] >= 1
    assert body["embedding_provider"] == "local"
