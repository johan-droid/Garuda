"""In-process TTL cache with per-category expiry, staleness and ETag support.

Expiry is per data category, not global: a health outbreak advisory and a
census table have very different update rhythms, and a single TTL would
either serve stale public-health information or re-fetch census data
constantly.

Expired entries are retained rather than deleted. That is what lets `fetch()`
answer "we hold something, but it is past its TTL" when the upstream is
unreachable, instead of collapsing an upstream blip into an outage. Every read
therefore reports a status, so an expired answer is always labelled `stale`
and never passed off as current.

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
from dataclasses import dataclass
from typing import Any, Callable, NamedTuple

from app.core.config import settings
from app.domain.common import DataStatus

# Per-category TTLs. Keyed by the same domain names used by the freshness
# service so the two stay understandable side by side.
CATEGORY_TTL_SECONDS: dict[str, int] = {
    "demographics": settings.CACHE_TTL_DEMOGRAPHICS_SECONDS,
    "services": settings.CACHE_TTL_FACILITIES_SECONDS,
    "infrastructure": settings.CACHE_TTL_FACILITIES_SECONDS,
    "environment": settings.CACHE_TTL_FACILITIES_SECONDS,
    "resilience": settings.CACHE_TTL_FACILITIES_SECONDS,
    "history_culture": settings.CACHE_TTL_DEMOGRAPHICS_SECONDS,
    "weather_disasters": 1_800,
    "health": settings.CACHE_TTL_HEALTH_ADVISORY_SECONDS,
    "health_outbreak": settings.CACHE_TTL_HEALTH_OUTBREAK_SECONDS,
    "place_lookup": settings.CACHE_TTL_PLACE_LOOKUP_SECONDS,
}

DEFAULT_TTL_SECONDS = 60


def ttl_for(category: str) -> int:
    """Return the TTL in seconds for a cache category."""
    return CATEGORY_TTL_SECONDS.get(category, DEFAULT_TTL_SECONDS)


@dataclass
class CacheEntry:
    """One cached value and everything needed to judge it.

    `source` is the category the value was cached under, which is what picks
    the TTL. `stale` is set only when the entry was actually served past its
    expiry, so it records a decision rather than restating the clock.
    """

    value: Any
    cached_at: float
    expires_at: float
    source: str = ""
    stale: bool = False


class CacheResult(NamedTuple):
    """What a read produced, and how much of it the caller may believe."""

    value: Any | None
    status: DataStatus
    from_cache: bool


class EnhancedCache:
    """Bounded TTL cache with LRU eviction and an explicit stale fallback."""

    def __init__(self, max_entries: int | None = None) -> None:
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_entries = max_entries if max_entries is not None else settings.CACHE_MAX_ENTRIES
        self.hits = 0
        self.misses = 0
        self.stale_served = 0

    @staticmethod
    def _expired(entry: CacheEntry, now: float) -> bool:
        return now >= entry.expires_at

    def get(self, key: str) -> Any | None:
        """Return a *fresh* cached value, or None when absent or expired.

        An expired entry is reported as a miss but deliberately retained:
        `fetch()` still needs it as the fallback when the upstream is down.
        """
        entry = self._entries.get(key)
        if entry is None:
            self.misses += 1
            return None
        if self._expired(entry, time.monotonic()):
            self.misses += 1
            return None
        self._entries.move_to_end(key)
        self.hits += 1
        return entry.value

    def put(self, key: str, value: Any, ttl_seconds: int | None = None, source: str = "") -> None:
        """Store a value, expiring on the source's TTL (or an explicit override)."""
        now = time.monotonic()
        ttl = ttl_seconds if ttl_seconds is not None else ttl_for(source)
        self._entries[key] = CacheEntry(
            value=value,
            cached_at=now,
            expires_at=now + ttl,
            source=source,
        )
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    def fetch(
        self,
        key: str,
        producer: Callable[[], Any],
        *,
        source: str = "",
        ttl_seconds: int | None = None,
    ) -> CacheResult:
        """Read through the cache, saying exactly what the answer is worth.

        Four outcomes, and none of them is silent:

          * fresh entry      -> cached value, `current`
          * stale, upstream answers -> refreshed value, `current`
          * stale, upstream fails   -> expired value, `stale`
          * nothing cached, upstream fails -> no value, `unavailable`
        """
        entry = self._entries.get(key)
        now = time.monotonic()

        if entry is not None and not self._expired(entry, now):
            self._entries.move_to_end(key)
            self.hits += 1
            return CacheResult(entry.value, DataStatus.CURRENT, True)

        # Absent or past its TTL. Only an upstream that answers may refresh
        # it; if it does not, the expired copy stands in, clearly labelled.
        try:
            value = producer()
        except Exception:
            self.misses += 1
            if entry is None:
                return CacheResult(None, DataStatus.UNAVAILABLE, False)
            # The label is what keeps this honest: an expired answer offered
            # as `stale` lets the caller discount it, where offering it
            # as current would not.
            entry.stale = True
            self.stale_served += 1
            return CacheResult(entry.value, DataStatus.STALE, True)

        self.misses += 1
        self.put(key, value, ttl_seconds, source)
        return CacheResult(value, DataStatus.CURRENT, False)

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
            "stale_entries": sum(1 for entry in self._entries.values() if entry.stale),
            "max_entries": self._max_entries,
            "hits": self.hits,
            "misses": self.misses,
            "stale_served": self.stale_served,
            "hit_rate": round(self.hits / total, 4) if total else 0.0,
        }


_cache = EnhancedCache()


def get_cache() -> EnhancedCache:
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
    from the cache. An expired value is a miss here: this path has no way to
    tell a caller that an answer is stale, so it re-fetches instead.
    """
    full_key = f"{category}:{key}"
    cached = _cache.get(full_key)
    if cached is not None:
        return cached, True
    value = producer()
    _cache.put(full_key, value, ttl_seconds, source=category)
    return value, False
