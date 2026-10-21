"""Safe error responses.

Public error bodies must never contain stack traces, SQL statements, file
system paths, environment values, or internal hostnames. Operators still get
full diagnostics through the structured logs, keyed by the request ID that is
returned to the caller in the ``X-Request-ID`` header.
"""

from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, request_id_ctx

logger = get_logger("garuda.errors")

# Public-safe messages for common failure modes.
SAFE_MESSAGES: dict[int, str] = {
    400: "The request could not be processed.",
    401: "Authentication is required for this operation.",
    403: "You do not have permission to perform this operation.",
    404: "The requested resource was not found.",
    405: "The HTTP method is not allowed for this endpoint.",
    413: "The request payload is too large.",
    415: "The request media type is not supported.",
    422: "The request could not be validated.",
    429: "Too many requests. Please slow down and retry later.",
    500: "An internal error occurred. The incident has been logged.",
    502: "An upstream data provider could not be reached.",
    503: "The service is temporarily unable to handle this request.",
    504: "An upstream data provider timed out.",
}


def error_body(
    status_code: int,
    code: str,
    message: str | None = None,
    details: Any = None,
) -> dict[str, Any]:
    """Build a uniform, safe error body."""
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message or SAFE_MESSAGES.get(status_code, "The request could not be completed."),
            "status": status_code,
            "request_id": request_id_ctx.get(),
        }
    }
    if details is not None:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers that convert all errors into safe, structured responses."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        # Preserve explicit, operator-authored messages (e.g. rate limit guidance).
        message = detail if isinstance(detail, str) else None
        if exc.status_code >= 500:
            logger.error(
                "http_error",
                extra={"extra_fields": {"path": request.url.path, "status": exc.status_code}},
            )
            message = None
        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.status_code, _code_for(exc.status_code), message),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Field-level messages only - they describe the client's own input and
        # never leak server internals.
        details = [
            {
                "field": ".".join(str(part) for part in err.get("loc", ())[1:]) or "body",
                "message": err.get("msg", "invalid value"),
                "type": err.get("type", "value_error"),
            }
            for err in exc.errors()
        ][:20]
        logger.info(
            "validation_error",
            extra={"extra_fields": {"path": request.url.path, "error_count": len(details)}},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_body(422, "validation_error", details=details),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log the full detail server-side; return an opaque body publicly.
        logger.exception(
            "unhandled_exception",
            extra={"extra_fields": {"path": request.url.path, "error_type": type(exc).__name__}},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body(500, "internal_error"),
        )


def _code_for(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        413: "payload_too_large",
        415: "unsupported_media_type",
        422: "validation_error",
        429: "rate_limited",
        500: "internal_error",
        502: "upstream_error",
        503: "service_unavailable",
        504: "upstream_timeout",
    }.get(status_code, "error")


def http_error(status_code: int, message: str | None = None, code: str | None = None) -> HTTPException:
    """Build an HTTPException carrying a safe message."""
    return HTTPException(status_code=status_code, detail=message or SAFE_MESSAGES.get(status_code))
