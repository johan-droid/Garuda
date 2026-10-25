"""Circuit breaker for outbound upstream calls.

Retries are already handled inside the provider adapters; what they cannot do
is stop. An upstream that stays down is still hit on every incoming request,
each attempt burning its full timeout, so one dead provider drags down every
request that touches it. The breaker counts consecutive failures and, once
satisfied the upstream is unhealthy, refuses to call it for a while instead
answering immediately with a typed error the adapters already turn into
`unavailable` observations.

Three states:

  CLOSED    calls pass; consecutive failures are counted.
  OPEN      calls are refused without any network attempt.
  HALF_OPEN one trial call is admitted after the cooldown. It either succeeds
            (back to CLOSED) or fails (straight back to OPEN, cooldown and
            all, so a dead upstream cannot be retried in a tight loop).

Breakers are process-wide, keyed by upstream, because routes construct a
fresh adapter per request: a per-instance breaker would never live long
enough to notice a persistent failure.

Not synchronized. Under a race two threads may both be admitted in
HALF_OPEN; that costs one extra upstream call, never a wrong answer.
"""

import time
from collections.abc import Callable
from enum import Enum

DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_RECOVERY_TIMEOUT_SECONDS = 30.0
DEFAULT_SUCCESS_THRESHOLD = 1


class CircuitState(str, Enum):
    """Where the breaker currently stands."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """The upstream is being skipped; no request was made."""


class CircuitBreaker:
    """Refuses calls to an upstream that keeps failing.

    `before_request()` decides admission, `record_success()` and
    `record_failure()` report the outcome. A caller that forgets to report
    simply leaves the breaker where it was, which fails safe in the sense
    that nothing is refused wrongly.
    """

    def __init__(
        self,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        recovery_timeout: float = DEFAULT_RECOVERY_TIMEOUT_SECONDS,
        success_threshold: int = DEFAULT_SUCCESS_THRESHOLD,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self._clock = clock
        self.state = CircuitState.CLOSED
        self.consecutive_failures = 0
        self._half_open_successes = 0
        self._opened_at = 0.0

    @property
    def is_open(self) -> bool:
        return self.state is CircuitState.OPEN

    def before_request(self) -> None:
        """Raise `CircuitOpenError` if this call must not be made."""
        if self.state is CircuitState.CLOSED:
            return
        if self.state is CircuitState.OPEN:
            elapsed = self._clock() - self._opened_at
            if elapsed < self.recovery_timeout:
                raise CircuitOpenError(
                    f"upstream skipped after {self.failure_threshold} consecutive "
                    f"failures; circuit half-opens in {self.recovery_timeout - elapsed:.0f}s"
                )
            self.state = CircuitState.HALF_OPEN
            self._half_open_successes = 0
            return
        # HALF_OPEN: let the single trial call through.

    def record_success(self) -> None:
        """Report a completed call that the upstream answered."""
        if self.state is CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            if self._half_open_successes >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.consecutive_failures = 0
                self._half_open_successes = 0
            return
        if self.state is CircuitState.CLOSED:
            # Only *consecutive* failures count: a working upstream earns
            # back its allowance rather than carrying a lifetime tally.
            self.consecutive_failures = 0

    def record_failure(self) -> None:
        """Report a call the upstream did not answer (retries already spent)."""
        if self.state is CircuitState.OPEN:
            return  # already refusing; must not push the cooldown out
        if self.state is CircuitState.HALF_OPEN:
            self._open()
            return
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self._open()

    def _open(self) -> None:
        self.state = CircuitState.OPEN
        self._opened_at = self._clock()
        self.consecutive_failures = 0
        self._half_open_successes = 0


_BREAKERS: dict[str, CircuitBreaker] = {}


def breaker_for(key: str) -> CircuitBreaker:
    """Return the process-wide breaker for one upstream, creating it if new."""
    breaker = _BREAKERS.get(key)
    if breaker is None:
        breaker = CircuitBreaker()
        _BREAKERS[key] = breaker
    return breaker


def reset_breakers() -> None:
    """Forget every breaker. Tests use this to start from a known state."""
    _BREAKERS.clear()
