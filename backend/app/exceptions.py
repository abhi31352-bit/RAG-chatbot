"""Custom exceptions and application-wide exception handlers."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("rag-chatbot")


class AppError(Exception):
    """Base class for application errors."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "INTERNAL_ERROR"
    message = "An unexpected error occurred."

    def __init__(self, message: str = None, details: dict = None):
        self.message = message or self.message
        self.details = details or {}
        super().__init__(self.message)


class InvalidFileTypeError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "INVALID_FILE_TYPE"
    message = "Unsupported file type."


class FileTooLargeError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "FILE_TOO_LARGE"
    message = "File exceeds the maximum allowed size."


class EmptyFileError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "EMPTY_FILE"
    message = "Uploaded file has no content."


class DocumentNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "DOCUMENT_NOT_FOUND"
    message = "The requested document does not exist."


class ProcessingError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "PROCESSING_ERROR"
    message = "Failed to process the document."


class LLMUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "LLM_UNAVAILABLE"
    message = "The language model service is temporarily unavailable."


class EmbeddingUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "EMBEDDING_UNAVAILABLE"
    message = "The embedding service is temporarily unavailable."


class EmbeddingMismatchError(AppError):
    """Raised when a query uses a different provider than the stored index.

    The two providers produce different vector widths, so mixing them would
    silently return meaningless neighbours. This is a server-side state
    problem, not something the client can fix, hence a 409 with the remedy in
    the message rather than a generic 500.
    """

    status_code = status.HTTP_409_CONFLICT
    code = "EMBEDDING_MISMATCH"
    message = "The vector index was built with a different embedding provider."


def _error_body(code: str, message: str, details: dict = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _safe_validation_errors(exc: RequestValidationError) -> list:
    """Make Pydantic's error list JSON-serializable.

    A custom validator's ``ValueError`` is carried through in ``ctx`` as a live
    exception object. ``json.dumps`` cannot encode that, so passing
    ``exc.errors()`` straight into a JSONResponse turns any such validation
    failure into a 500 instead of the intended 422 envelope.
    """
    sanitized = []
    for error in exc.errors():
        item = {k: v for k, v in error.items() if k != "ctx"}
        if "ctx" in error:
            item["ctx"] = {k: str(v) for k, v in (error["ctx"] or {}).items()}
        # `input` can be an arbitrary object for some validators.
        if not isinstance(item.get("input"), (str, int, float, bool, type(None), list)):
            item["input"] = str(item.get("input"))
        sanitized.append(item)
    return sanitized


def register_exception_handlers(app: FastAPI):
    """Attach handlers so all errors return a consistent JSON envelope."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        logger.warning("%s: %s", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                "VALIDATION_ERROR",
                "Request validation failed.",
                {"errors": _safe_validation_errors(exc)},
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("INTERNAL_ERROR", "An unexpected error occurred."),
        )
