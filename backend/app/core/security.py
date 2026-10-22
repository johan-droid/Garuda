"""HTTP security headers.

The default policy is intentionally restrictive. The API serves JSON only, so
the CSP does not need to allow inline scripts, and the frontend is served from a
separate origin (the Vite dev server / static host), so `frame-ancestors 'none'`
is appropriate.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

# Conservative default CSP for a JSON API. The frontend is a separate origin.
DEFAULT_CSP = (
    "default-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'"
)

# Cross-origin isolation policy is intentionally NOT set: the API is consumed
# cross-origin by the PWA and needs CORS to function.
REFERRER_POLICY = "strict-origin-when-cross-origin"
X_CONTENT_TYPE_OPTIONS = "nosniff"
X_FRAME_OPTIONS = "DENY"
CROSS_ORIGIN_OPENER_POLICY = "same-origin"
CROSS_ORIGIN_RESOURCE_POLICY = "cross-origin"
PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), "
    "microphone=(), payment=(), usb=()"
)

DOCS_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "frame-ancestors 'none'; "
    "object-src 'none'"
)


def build_csp() -> str:
    """Return the CSP string, honouring an operator override."""
    override = settings.CSP_DIRECTIVES
    if override:
        # Guard against an override that would disable the key protections.
        lowered = override.lower()
        if "frame-ancestors" not in lowered:
            override = f"{override.rstrip('; ')}; frame-ancestors 'none'"
        if "object-src" not in lowered:
            override = f"{override.rstrip('; ')}; object-src 'none'"
        return override
    return DEFAULT_CSP


class SecurityHeadersMiddleware:
    """ASGI middleware that adds hardening headers to every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                self._apply(headers, path=path)
            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _apply(self, headers: list[tuple[bytes, bytes]], path: str = "") -> None:
        existing = {key.decode("latin-1").lower() for key, _ in headers}

        def add(name: str, value: str) -> None:
            if name.lower() not in existing:
                headers.append((name.encode("latin-1"), value.encode("latin-1")))

        csp = DOCS_CSP if path in ("/docs", "/redoc", "/openapi.json") else build_csp()
        add("Content-Security-Policy", csp)
        add("X-Content-Type-Options", X_CONTENT_TYPE_OPTIONS)
        add("X-Frame-Options", X_FRAME_OPTIONS)
        add("Referrer-Policy", REFERRER_POLICY)
        add("Cross-Origin-Opener-Policy", CROSS_ORIGIN_OPENER_POLICY)
        add("Cross-Origin-Resource-Policy", CROSS_ORIGIN_RESOURCE_POLICY)
        add("Permissions-Policy", PERMISSIONS_POLICY)
        # Do not advertise the server implementation (Starlette sets `server`).
        if "server" in existing:
            for index, (key, _) in enumerate(headers):
                if key.decode("latin-1").lower() == "server":
                    headers[index] = (key, b"garuda")
                    break

        if settings.ENABLE_HSTS:
            add(
                "Strict-Transport-Security",
                f"max-age={settings.SECURITY_HEADERS_MAX_AGE}; includeSubDomains",
            )
