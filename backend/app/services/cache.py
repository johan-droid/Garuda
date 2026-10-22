"""In-process TTL cache with per-category expiry and ETag support.

Expiry is per data category, not global: a health outbreak advisory and a
census table have very different update rhythms, and a single TTL would
either serve stale public-health information or re-fetch census data
constantly.

Limitations (documented in docs/PRODUCTION.md):
  * The cache is per-process. With multiple API instances each instance keeps
    its own cache, so a change is visible on all instances only after the TTL
    expires.
  * Cache entries are lost on restart, which is acceptable because the
    underlying data is persisted in the database.
"""

import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Callable

from app.core.config import settings

# Per-category TTLs. Keyed by the same domain names used by the freshness
# service so the two stay understandable side by side.
CATEGORY_TTL_SECONDS: dict[str, int] = {
    "demographics": settings.CACHE_TTL_DEMOGRAPHICS_SECONDS,
    "services": settings.CACHE_TTL_FACILITIES_SECONDS,
    "infrastructure": settings.CACHE_TTL_FACILITIES_SECONDS,
    "environment": settings.CACHE_TTL_FACILITIES_SECONDS,
    "resilience": settings.CACHE_TTL_FACILITIES_SECONDS,
    "health": settings.CACHE_TTL_HEALTH_ADVISORY_SECONDS,
    "health_outbreak": settings.CACHE_TTL_HEALTH_OUTBREAK_SECONDS,
    "place_lookup": settings.CACHE_TTL_PLACE_LOOKUP_SECONDS,
}

DEFAULT_TTL_SECONDS = 60


def ttl_for(category: str) -> int:
    """Return the TTL in seconds for a cache category."""
    return CATEGORY_TTL_SECONDS.get(category, DEFAULT_TTL_SECONDS)


class TTLCache:
    """Bounded TTL cache with LRU eviction."""

    def __init__(self, max_entries: int | None = None) -> None:
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max_entries = max_entries if max_entries is not None else settings.CACHE_MAX_ENTRIES
        self.hits = 0
        self.misses = 0

    def _expired(self, expires_at: float) -> bool:
        return time.monotonic() >= expires_at

    def get(self, key: str) -> Any | None:
        """Return a cached value, or None when absent or expired."""
        entry = self._entries.get(key)
        if entry is None:
            self.misses += 1
            return None
        expires_at, value = entry
        if self._expired(expires_at):
            del self._entries[key]
            self.misses += 1
            return None
        self._entries.move_to_end(key)
        self.hits += 1
        return value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Store a value with the category's TTL (or an explicit override)."""
        ttl = ttl_seconds if ttl_seconds is not None else DEFAULT_TTL_SECONDS
        self._entries[key] = (time.monotonic() + ttl, value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def invalidate_prefix(self, prefix: str) -> int:
        """Drop every entry whose key starts with the prefix. Returns the count."""
        doomed = [key for key in self._entries if key.startswith(prefix)]
        for key in doomed:
            del self._entries[key]
        return len(doomed)

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()

    def stats(self) -> dict[str, Any]:
        """Return cache statistics for the health endpoint."""
        total = self.hits + self.misses
        return {
            "entries": len(self._entries),
            "max_entries": self._max_entries,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 4) if total else 0.0,
        }


_cache = TTLCache()


def get_cache() -> TTLCache:
    """Return the process-wide cache instance."""
    return _cache


def compute_etag(payload: Any) -> str:
    """Compute a strong ETag for a response payload.

    The digest covers the serialised body, so any change in content changes
    the ETag and clients revalidate correctly.
    """
    try:
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    except (TypeError, ValueError):
        encoded = repr(payload).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f'"{digest[:32]}"'


def cached_response(
    category: str,
    key: str,
    producer: Callable[[], Any],
    ttl_seconds: int | None = None,
) -> tuple[Any, bool]:
    """Return a cached value, computing it with `producer` on a miss.

    Returns the value and a boolean that is True when the value was served
    from the cache.
    """
    full_key = f"{category}:{key}"
    cached = _cache.get(full_key)
    if cached is not None:
        return cached, True
    value = producer()
    _cache.set(full_key, value, ttl_seconds if ttl_seconds is not None else ttl_for(category))
    return value, False
