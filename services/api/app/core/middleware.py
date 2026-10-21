"""Request middleware: correlation IDs, access logging, rate limiting, size caps."""

import time
from typing import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.errors import error_body
from app.core.logging import get_logger, new_request_id, request_id_ctx
from app.core.ratelimit import RateLimitCategory, check_rate_limit

logger = get_logger("garuda.access")

REQUEST_ID_HEADER = "X-Request-ID"

# Paths that must stay reachable for orchestration even under load.
# Matched on the path suffix so they work under any API prefix.
EXEMPT_PATHS = {"/health", "/health/live", "/health/ready", "/docs", "/openapi.json", "/redoc"}


def _is_exempt(path: str) -> bool:
    """Return True when the path is an orchestration endpoint."""
    return path in EXEMPT_PATHS or any(path.endswith(exempt) for exempt in EXEMPT_PATHS)


def _path_segments(path: str) -> list[str]:
    """Split a path into its non-empty segments."""
    return [segment for segment in path.split("/") if segment]


def rate_limit_category(path: str) -> str:
    """Resolve the rate-limit bucket for a path.

    The check is segment-based so it works regardless of the API prefix and
    cannot be fooled by a path such as `/places-of-interest`.
    """
    segments = _path_segments(path)
    if "admin" in segments:
        return RateLimitCategory.ADMIN
    if "search" in segments or "places" in segments:
        return RateLimitCategory.SEARCH
    return RateLimitCategory.PUBLIC


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request ID, log the request, and enforce limits."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming_id = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming_id[:64] if incoming_id.isprintable() and len(incoming_id) <= 64 else new_request_id()
        token = request_id_ctx.set(request_id)
        request.state.request_id = request_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            request_id_ctx.reset(token)

        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "client": client_identifier(request),
                }
            },
        )
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies before they are parsed."""

    def __init__(self, app, max_bytes: int | None = None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.max_bytes = max_bytes if max_bytes is not None else settings.MAX_REQUEST_BODY_BYTES

    def _limit_for(self, path: str) -> int:
        """Return the size ceiling that applies to a path.

        Administrative imports legitimately carry many rows, so they get their
        own (larger) ceiling. Every other path keeps the default limit.
        """
        if "import" in [segment for segment in path.split("/") if segment]:
            return max(self.max_bytes, settings.MAX_IMPORT_PAYLOAD_BYTES)
        return self.max_bytes

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        content_length = request.headers.get("content-length")
        max_bytes = self._limit_for(request.url.path)
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content=error_body(400, "bad_request", "Invalid Content-Length header."),
                )
            if declared > max_bytes:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content=error_body(413, "payload_too_large"),
                    headers={"Retry-After": "60"},
                )
        response = await call_next(request)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client request throttling with standard RateLimit-* headers."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if _is_exempt(path) or not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        category = rate_limit_category(path)

        result = check_rate_limit(client_identifier(request), category, path)
        if not result.allowed:
            logger.info(
                "rate_limited",
                extra={"extra_fields": {"path": path, "client": client_identifier(request), "category": category}},
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content=error_body(429, "rate_limited"),
                headers={
                    "Retry-After": str(max(1, result.retry_after)),
                    "RateLimit-Limit": str(result.limit),
                    "RateLimit-Remaining": "0",
                    "RateLimit-Reset": str(result.reset_after),
                },
            )

        response = await call_next(request)
        response.headers["RateLimit-Limit"] = str(result.limit)
        response.headers["RateLimit-Remaining"] = str(result.remaining)
        response.headers["RateLimit-Reset"] = str(result.reset_after)
        return response


def client_identifier(request: Request) -> str:
    """Resolve the client identity used for rate limiting.

    Proxy headers are only trusted when the deployment explicitly declares
    trusted proxy hops; otherwise a client could spoof its IP and bypass limits.
    """
    if settings.TRUSTED_PROXY_HOPS > 0:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parts = [part.strip() for part in forwarded.split(",") if part.strip()]
            if parts:
                index = max(0, len(parts) - settings.TRUSTED_PROXY_HOPS)
                return parts[index][:64]
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()[:64]
    client = request.client
    if client and client.host:
        return client.host[:64]
    return "unknown"
