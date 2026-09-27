"""Text extraction from uploaded documents.

The extension allowlist here is the real security control: each extension maps
to exactly one parser, so a file can never be interpreted as a different type.
MIME types from the browser are advisory only (browsers and `curl` disagree
about what they send for `.md` and `.docx`).
"""

import io
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger("rag-chatbot")

PDF = "pdf"
TXT = "txt"
DOCX = "docx"
MD = "md"

#: Extensions accepted by the upload endpoint (no leading dot).
ALLOWED_EXTENSIONS = {PDF, TXT, DOCX, MD}

#: Human-readable labels used in error messages.
SUPPORTED_TYPES_LABEL = "PDF, TXT, DOCX, MD"


class UnsupportedFileTypeError(ValueError):
    """Raised when a file extension has no registered parser."""


class DocumentParseError(ValueError):
    """Raised when a file cannot be parsed as its declared type."""


def normalize_extension(file_type: str) -> str:
    """Accept `pdf`, `.pdf`, or `PDF` and return the canonical `pdf`."""
    if not file_type:
        raise UnsupportedFileTypeError("Missing file extension")
    return file_type.strip().lower().lstrip(".")


class FileHandler:
    """Extracts plain text from the supported document formats."""

    def parse(self, contents: bytes, file_type: str) -> str:
        """Return the text content of `contents`.

        Raises UnsupportedFileTypeError for unknown extensions and
        DocumentParseError when the payload does not match its extension.
        """
        ext = normalize_extension(file_type)
        if ext == PDF:
            return self._parse_pdf(contents)
        if ext == DOCX:
            return self._parse_docx(contents)
        if ext in (TXT, MD):
            return self._parse_text(contents)
        raise UnsupportedFileTypeError(f"Unsupported file type: {ext}")

    def parse_with_pages(
        self, contents: bytes, file_type: str
    ) -> Tuple[str, List[Tuple[int, int]]]:
        """Like :meth:`parse` but also returns page boundaries.

        The second element is a list of ``(page_number, char_offset)`` pairs
        giving where each page begins in the returned text, sorted by offset.
        Only PDFs have real pages; for every other format the list is empty and
        callers should treat page numbers as unknown.
        """
        ext = normalize_extension(file_type)
        if ext == PDF:
            return self._parse_pdf_with_pages(contents)
        return self.parse(contents, ext), []

    # -- Parsers ----------------------------------------------------------

    def _parse_pdf(self, contents: bytes) -> str:
        text, _ = self._parse_pdf_with_pages(contents)
        return text

    def _parse_pdf_with_pages(
        self, contents: bytes
    ) -> Tuple[str, List[Tuple[int, int]]]:
        try:
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError
        except ImportError as exc:  # pragma: no cover
            raise DocumentParseError("pypdf is not installed") from exc

        try:
            reader = PdfReader(io.BytesIO(contents))
        except PdfReadError as exc:
            raise DocumentParseError(
                "File is not a valid PDF. Scanned/image-only PDFs need OCR, "
                "which is not configured."
            ) from exc
        except Exception as exc:
            raise DocumentParseError(f"Could not read PDF: {exc}") from exc

        # An encrypted PDF is a common upload; fail clearly instead of hanging.
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")
            except Exception as exc:
                raise DocumentParseError(
                    "PDF is password protected and cannot be read"
                ) from exc

        parts: List[str] = []
        page_boundaries: List[Tuple[int, int]] = []
        cursor = 0
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                logger.warning(
                    "Skipping unreadable page %s of a PDF", page_number, exc_info=True
                )
                continue
            if not page_text.strip():
                # A blank page contributes no text, so it is not a boundary.
                continue
            if parts:
                parts.append("\n\n")
                cursor += 2
            page_boundaries.append((page_number, cursor))
            parts.append(page_text)
            cursor += len(page_text)

        return "".join(parts), page_boundaries

    def _parse_docx(self, contents: bytes) -> str:
        try:
            import docx
        except ImportError as exc:  # pragma: no cover
            raise DocumentParseError("python-docx is not installed") from exc

        try:
            document = docx.Document(io.BytesIO(contents))
        except Exception as exc:
            raise DocumentParseError(
                "File is not a valid DOCX (it may be a legacy .doc file)"
            ) from exc

        parts = [p.text for p in document.paragraphs if p.text.strip()]

        # Tables carry real content in many lecture slides and handouts.
        for table in document.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))

        return "\n".join(parts)

    def _parse_text(self, contents: bytes) -> str:
        # utf-8-sig must come first: plain "utf-8" also decodes a BOM, but
        # leaves the U+FEFF character at the start of the text.
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return contents.decode(encoding)
            except UnicodeDecodeError:
                continue
        # latin-1 never fails, so this is unreachable in practice.
        return contents.decode("utf-8", errors="replace")


_file_handler: Optional[FileHandler] = None


def get_file_handler() -> FileHandler:
    """Return the shared FileHandler instance."""
    global _file_handler
    if _file_handler is None:
        _file_handler = FileHandler()
    return _file_handler
