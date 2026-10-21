"""SSRF-safe HTTP client for upstream data providers.

Every outbound request must pass through this module. It guards against
Server-Side Request Forgery by:

  * only allowing http/https schemes,
  * resolving the hostname and rejecting private, loopback, link-local,
    multicast, and otherwise reserved IP ranges,
  * re-checking the resolved address on every redirect (no redirect following
    to an internal host),
  * capping the response size,
  * applying a strict timeout and bounded retry with exponential backoff.

Private addresses are only permitted when `ALLOW_PRIVATE_UPSTREAM` is enabled,
which is intended for local development against a mock server.
"""

import ipaddress
import socket
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("garuda.upstream")

ALLOWED_SCHEMES = {"http", "https"}


class UnsafeURLError(ValueError):
    """Raised when a URL fails the SSRF safety checks."""


def _is_public_address(host: str) -> bool:
    """Return True when the host resolves only to public addresses."""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Could not resolve host '{host}'.") from exc

    if not infos:
        raise UnsafeURLError(f"Host '{host}' did not resolve to any address.")

    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            raise UnsafeURLError(f"Host '{host}' resolved to an invalid address.") from None
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def validate_url(url: str) -> str:
    """Validate a URL for safe outbound use. Returns the URL if it is safe."""
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError("Only http and https URLs are allowed.")

    if not parsed.hostname:
        raise UnsafeURLError("The URL must include a hostname.")

    if parsed.username or parsed.password:
        raise UnsafeURLError("Credentials must not be embedded in the URL.")

    if not settings.ALLOW_PRIVATE_UPSTREAM:
        if not _is_public_address(parsed.hostname):
            raise UnsafeURLError(
                f"Host '{parsed.hostname}' resolves to a private or reserved address."
            )
    return url


def _is_safe_redirect(location: str) -> bool:
    """Validate a redirect target.

    The location must already be resolved against the current URL. A relative
    `Location` header (e.g. `/v2/data`) has no scheme of its own, so it must
    be joined with the current URL *before* validation, otherwise every
    legitimate relative redirect would be rejected as scheme-less.
    """
    try:
        validate_url(location)
    except UnsafeURLError:
        return False
    return True


def _resolve_redirect(current_url: str, location: str) -> str:
    """Join a `Location` header against the current URL.

    Returns the absolute URL. Raises `UnsafeURLError` when the header is
    missing or cannot be resolved.
    """
    if not location:
        raise UnsafeURLError("Upstream returned a redirect without a Location header.")

    resolved = urljoin(current_url, location)
    if resolved == current_url:
        raise UnsafeURLError("Upstream returned a redirect to the same URL.")
    return resolved


def build_client(timeout: float | None = None) -> httpx.Client:
    """Create an HTTP client with the safe redirect policy applied."""
    request_timeout = timeout if timeout is not None else float(settings.UPSTREAM_TIMEOUT_SECONDS)
    return httpx.Client(
        timeout=httpx.Timeout(request_timeout),
        follow_redirects=False,  # redirects are validated manually
        headers={
            "User-Agent": settings.UPSTREAM_USER_AGENT,
            "Accept": "application/json",
        },
        limits=httpx.Limits(max_connections=settings.UPSTREAM_MAX_CONCURRENT),
    )


def _max_redirects() -> int:
    return 3


def fetch_json(
    url: str,
    *,
    client: httpx.Client | None = None,
    headers: dict[str, str] | None = None,
    max_bytes: int = 5_000_000,
) -> Any:
    """Fetch and parse a JSON document from an upstream provider.

    Raises `httpx.HTTPError` for transport failures and `UnsafeURLError` when
    the target is not safe to contact.
    """
    validate_url(url)
    owns_client = client is None
    http = client or build_client()
    try:
        current_url = url
        for _ in range(_max_redirects() + 1):
            response = http.get(current_url, headers=headers)
            if response.is_redirect:
                location = response.headers.get("location", "")
                # Resolve first: a relative Location has no scheme of its own
                # and would fail validation if checked before joining.
                next_url = _resolve_redirect(current_url, location)
                if not _is_safe_redirect(next_url):
                    raise UnsafeURLError("Upstream returned an unsafe redirect target.")
                current_url = next_url
                continue
            response.raise_for_status()
            content = response.content
            if len(content) > max_bytes:
                raise ValueError("Upstream response exceeded the maximum accepted size.")
            return response.json()
        raise UnsafeURLError("Upstream exceeded the maximum number of redirects.")
    finally:
        if owns_client:
            http.close()
