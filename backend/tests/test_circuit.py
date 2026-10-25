"""Circuit breaker: stop calling an upstream that has proved it is down.

Retries live inside the provider adapters, but retries have no opinion about
whether to keep trying tomorrow. Without a breaker, every incoming request
pays a dead upstream its full timeout, so one broken provider slows the whole
process. These tests pin the four transitions and, above all, that an open
breaker refuses the call *before* any network attempt is made.
"""

import httpx
import pytest

from app.domain.common import DataStatus
from app.services.circuit import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    breaker_for,
)
from app.services.provider_adapters import IMDWeatherAdapter

# Public test IP: no DNS resolution, and no real traffic either - the client
# is always wired to a MockTransport below.
TEST_PUBLIC_BASE = "https://8.8.8.8/weather"


class FakeClock:
    """A clock the tests move by hand, so no test ever sleeps."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_reaching_the_failure_threshold_opens_the_breaker() -> None:
    breaker = CircuitBreaker(failure_threshold=3, clock=FakeClock())

    for _ in range(2):
        breaker.record_failure()
        breaker.before_request()  # still closed: no refusal yet
        assert breaker.state is CircuitState.CLOSED

    breaker.record_failure()

    assert breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        breaker.before_request()


def test_a_success_resets_the_consecutive_failure_count() -> None:
    """It is *consecutive* failures that matter, not a lifetime tally."""
    breaker = CircuitBreaker(failure_threshold=3, clock=FakeClock())

    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()

    assert breaker.state is CircuitState.CLOSED


def test_the_cooldown_half_opens_and_a_success_closes_it() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout=30.0,
        success_threshold=1,
        clock=clock,
    )
    breaker.record_failure()

    with pytest.raises(CircuitOpenError):
        breaker.before_request()  # still cooling down

    clock.now = 30.0
    breaker.before_request()
    assert breaker.state is CircuitState.HALF_OPEN

    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED
    breaker.before_request()  # admitted again


def test_a_failure_while_half_open_reopens_and_restarts_the_cooldown() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=30.0, clock=clock)
    breaker.record_failure()

    clock.now = 30.0
    breaker.before_request()
    assert breaker.state is CircuitState.HALF_OPEN

    breaker.record_failure()

    assert breaker.state is CircuitState.OPEN
    # The cooldown restarts from the new failure; without that, a dead
    # upstream would be retried in a tight loop forever.
    with pytest.raises(CircuitOpenError):
        breaker.before_request()
    clock.now = 59.0
    with pytest.raises(CircuitOpenError):
        breaker.before_request()
    clock.now = 60.0
    breaker.before_request()
    assert breaker.state is CircuitState.HALF_OPEN


def test_success_threshold_gates_the_close() -> None:
    clock = FakeClock()
    breaker = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout=0.0,
        success_threshold=2,
        clock=clock,
    )
    breaker.record_failure()
    breaker.before_request()

    breaker.record_success()
    assert breaker.state is CircuitState.HALF_OPEN, "one success is not enough yet"

    breaker.record_success()
    assert breaker.state is CircuitState.CLOSED


def test_an_open_breaker_short_circuits_before_any_network_attempt() -> None:
    """The point of the whole thing: a refused call must cost no timeout.

    The upstream here would answer 500 if it were reached at all, and each
    attempt would otherwise burn its own retry loop on top.
    """
    attempts: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)
        return httpx.Response(500, text="upstream is down")

    adapter = IMDWeatherAdapter(
        base_url=TEST_PUBLIC_BASE,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0,
        backoff_base=0,
    )

    breaker = breaker_for(f"IMDWeatherAdapter:{TEST_PUBLIC_BASE}")
    for _ in range(breaker.failure_threshold):
        breaker.record_failure()
    assert breaker.state is CircuitState.OPEN

    observations = adapter.fetch_observations("IN-OD-29")

    assert attempts == [], "an open breaker must never reach the network"
    assert len(observations) == 3, "the caller still gets an answer, just not data"
    assert all(o.quality_status is DataStatus.UNAVAILABLE for o in observations)
    assert "skipped" in observations[0].notes, "the reason must survive to the panel"


def test_a_failing_upstream_opens_its_breaker_after_a_full_retry_budget() -> None:
    """Failures are counted per request, not per attempt inside one request."""
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, text="upstream is down")

    def adapter() -> IMDWeatherAdapter:
        # A fresh adapter per call, as routes do: the breaker must outlive it.
        return IMDWeatherAdapter(
            base_url=TEST_PUBLIC_BASE,
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            max_retries=1,
            backoff_base=0,
        )

    breaker = breaker_for(f"IMDWeatherAdapter:{TEST_PUBLIC_BASE}")
    threshold = breaker.failure_threshold

    for _ in range(threshold):
        adapter().fetch_observations("IN-OD-29")

    assert breaker.state is CircuitState.OPEN
    attempts_before = attempts
    adapter().fetch_observations("IN-OD-29")
    assert attempts == attempts_before, "the refused call must not touch the network"


def test_breakers_are_shared_per_upstream_key() -> None:
    """Routes build a new adapter per request, so the state must outlive it."""
    first = breaker_for("IMDWeatherAdapter:https://example.invalid")
    second = breaker_for("IMDWeatherAdapter:https://example.invalid")
    other = breaker_for("NHMHealthAdapter:https://example.invalid")

    assert first is second
    assert first is not other
