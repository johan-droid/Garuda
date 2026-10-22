"""Rate limiting for public, search, and administrative endpoints.

Deployment note: this implementation keeps counters **in-process**. That is
correct for the documented single-instance deployment (one small API host) and
is deliberately dependency-free. If the service is scaled to multiple
instances, set ``RATE_LIMIT_ENABLED`` and switch to a shared backend (the
``RateLimiter`` protocol makes that a drop-in replacement) - an in-process
limiter silently stops limiting across instances.
"""

import time
from collections import OrderedDict
from typing import Iterable, Protocol

from app.core.config import settings


class RateLimitResult:
    """Outcome of a rate limit check."""

    __slots__ = ("allowed", "limit", "remaining", "retry_after", "reset_after")

    def __init__(self, allowed: bool, limit: int, remaining: int, retry_after: int, reset_after: int) -> None:
        self.allowed = allowed
        self.limit = limit
        self.remaining = remaining
        self.retry_after = retry_after
        self.reset_after = reset_after


class RateLimiter(Protocol):
    """Interface so a distributed limiter can be swapped in without touching callers."""

    def hit(self, key: str, limit: int, window_seconds: int = 60) -> RateLimitResult: ...


class InMemoryRateLimiter:
    """Fixed-window, in-process rate limiter.

    Uses a monotonic clock and bounded storage so it cannot grow without limit.
    """

    def __init__(self, max_keys: int = 100_000) -> None:
        self._counters: OrderedDict[str, tuple[float, int]] = OrderedDict()
        self._max_keys = max_keys

    def hit(self, key: str, limit: int, window_seconds: int = 60) -> RateLimitResult:
        if limit <= 0:
            return RateLimitResult(True, 0, 0, 0, 0)
        now = time.monotonic()
        prev = self._counters.get(key)
        if prev is None or (now - prev[0] >= window_seconds):
            window_start = now
            count = 0
        else:
            window_start, count = prev
        count += 1
        self._counters[key] = (window_start, count)
        self._counters.move_to_end(key)

        # Bound memory: evict the oldest windows first.
        while len(self._counters) > self._max_keys:
            self._counters.popitem(last=False)

        reset_after = max(0, int(window_seconds - (now - window_start)))
        remaining = max(0, limit - count)
        allowed = count <= limit
        retry_after = 0 if allowed else reset_after
        return RateLimitResult(allowed, limit, remaining, retry_after, reset_after)


_limiter: InMemoryRateLimiter = InMemoryRateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Return the active rate limiter."""
    return _limiter


def reset_rate_limiter() -> None:
    """Clear all counters. Used by tests."""
    _limiter._counters.clear()


class RateLimitCategory:
    """Named rate-limit buckets with per-category ceilings."""

    PUBLIC = "public"
    SEARCH = "search"
    ADMIN = "admin"


def limit_for(category: str, path: str) -> int:
    """Resolve the applicable limit for a category/path pair.

    Search and admin paths always get the tighter ceiling even if the caller
    mislabels the category, so a route cannot accidentally get a looser budget.
    """
    segments = [segment for segment in path.split("/") if segment]
    if category == RateLimitCategory.ADMIN or "admin" in segments:
        return settings.RATE_LIMIT_ADMIN_PER_MINUTE
    if category == RateLimitCategory.SEARCH or "search" in segments:
        return settings.RATE_LIMIT_SEARCH_PER_MINUTE
    return settings.RATE_LIMIT_PUBLIC_PER_MINUTE


def check_rate_limit(identifier: str, category: str, path: str) -> RateLimitResult:
    """Check and consume one unit of quota for the given client identifier."""
    if not settings.RATE_LIMIT_ENABLED:
        return RateLimitResult(True, 0, 0, 0, 0)
    limit = limit_for(category, path)
    return get_rate_limiter().hit(f"{category}:{identifier}", limit)


def iter_client_identifiers(headers: Iterable[tuple[str, str]]) -> list[str]:
    """Extract candidate client identifiers from headers (used by middleware)."""
    values: list[str] = []
    for key, value in headers:
        if key.lower() in {"x-forwarded-for", "x-real-ip"}:
            values.append(value.split(",")[0].strip())
    return values
