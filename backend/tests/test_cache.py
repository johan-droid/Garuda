"""Provenance-aware cache: the four states a reader can see.

A cache that only knows "hit or miss" cannot tell a caller that it is holding
an answer past its TTL, and a caller that cannot be told will either re-fetch
blindly or, worse, present an old answer as if it were the current one. These
tests pin the four outcomes so that serving an expired value is always
explicit, and never silent.
"""

import pytest

from app.domain.common import DataStatus
from app.services.cache import (
    CATEGORY_TTL_SECONDS,
    DEFAULT_TTL_SECONDS,
    EnhancedCache,
    cached_response,
    get_cache,
    ttl_for,
)


@pytest.fixture(autouse=True)
def _clean_process_cache() -> None:
    """`cached_response` writes to the process-wide cache; isolate it."""
    get_cache().clear()
    yield
    get_cache().clear()


def test_fresh_hit_serves_from_cache_without_calling_the_upstream() -> None:
    cache = EnhancedCache(max_entries=8)
    cache.put("k", "answer", ttl_seconds=60, source="health")

    calls: list[str] = []

    def producer() -> str:
        calls.append("called")
        return "newer"

    result = cache.fetch("k", producer, source="health")

    assert result.value == "answer"
    assert result.status is DataStatus.CURRENT
    assert result.from_cache is True
    assert calls == [], "a fresh entry must not trigger a fetch"


def test_stale_entry_is_refreshed_when_the_upstream_answers() -> None:
    cache = EnhancedCache(max_entries=8)
    cache.put("k", "old", ttl_seconds=-1, source="health")

    result = cache.fetch("k", lambda: "new", source="health")

    assert result.value == "new"
    assert result.status is DataStatus.CURRENT
    assert result.from_cache is False
    # The refresh is written back, so the next read is a fresh hit.
    assert cache.get("k") == "new"


def test_stale_entry_is_served_and_marked_stale_when_the_upstream_fails() -> None:
    cache = EnhancedCache(max_entries=8)
    cache.put("k", "old", ttl_seconds=-1, source="health")

    def unreachable() -> str:
        raise RuntimeError("upstream down")

    result = cache.fetch("k", unreachable, source="health")

    assert result.value == "old", "an expired answer beats no answer, if labelled"
    assert result.status is DataStatus.STALE
    assert result.from_cache is True
    assert cache.stats()["stale_entries"] == 1
    assert cache.stats()["stale_served"] == 1


def test_nothing_cached_and_fetch_fails_is_unavailable() -> None:
    cache = EnhancedCache(max_entries=8)

    def unreachable() -> str:
        raise RuntimeError("upstream down")

    result = cache.fetch("k", unreachable, source="health")

    assert result.value is None, "'we do not know' must never be a value"
    assert result.status is DataStatus.UNAVAILABLE
    assert result.from_cache is False


def test_expired_entries_are_retained_as_the_stale_fallback() -> None:
    """A plain read must not throw the expired copy away.

    `get()` reports absence, but the entry has to survive for `fetch()` to
    fall back on. Deleting it here would leave the stale path with nothing to
    serve and quietly turn every upstream blip into an outage.
    """
    cache = EnhancedCache(max_entries=8)
    cache.put("k", "old", ttl_seconds=-1)

    assert cache.get("k") is None, "expired must never be served by get()"
    assert cache.stats()["entries"] == 1, "but it must still be there"


def test_source_selects_the_ttl_from_the_category_mapping() -> None:
    cache = EnhancedCache(max_entries=8)

    cache.put("k", "v", source="history_culture")
    entry = cache._entries["k"]
    assert entry.expires_at - entry.cached_at == CATEGORY_TTL_SECONDS["history_culture"]

    cache.put("k2", "v", source="not_a_registered_category")
    entry2 = cache._entries["k2"]
    assert entry2.expires_at - entry2.cached_at == DEFAULT_TTL_SECONDS
    assert ttl_for("not_a_registered_category") == DEFAULT_TTL_SECONDS


def test_cached_response_keeps_the_existing_caller_path_working() -> None:
    """place_service reads through this helper; its contract must not move."""
    calls: list[str] = []

    def producer() -> str:
        calls.append("called")
        return "value"

    value, was_hit = cached_response("health", "some-key", producer)
    assert (value, was_hit) == ("value", False)

    value, was_hit = cached_response("health", "some-key", producer)
    assert (value, was_hit) == ("value", True)
    assert calls == ["called"], "the second read must come from the cache"
