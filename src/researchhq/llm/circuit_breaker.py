"""Per-provider circuit breaker — open/half-open/closed state machine.

Protects the ensemble pipeline from cascading failures when a model provider
is flaky or rate-limited. A provider that fails repeatedly is taken out of
rotation for a configurable recovery window, then tested with a single probe
request before being fully restored.

State transitions:
  CLOSED    → OPEN       : failure_count reaches failure_threshold
  OPEN      → HALF_OPEN  : recovery_timeout seconds have elapsed since last failure
  HALF_OPEN → CLOSED     : one probe request succeeds
  HALF_OPEN → OPEN       : probe request fails (reset timer)

Usage:
    from researchhq.llm.circuit_breaker import get_breaker

    breaker = get_breaker("groq")
    if not breaker.allow_request():
        # skip this provider — circuit is open
        return error_result
    try:
        result = await provider.complete(...)
        breaker.record_success()
    except Exception:
        breaker.record_failure()
        raise
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CBState(str, Enum):
    CLOSED = "closed"        # normal — all requests pass through
    OPEN = "open"            # failing — requests rejected immediately
    HALF_OPEN = "half_open"  # testing recovery — one probe allowed


@dataclass
class CircuitBreaker:
    """Single-provider circuit breaker. Not thread-safe by design (asyncio single-thread)."""

    name: str
    failure_threshold: int = 5      # consecutive failures before tripping
    recovery_timeout: float = 60.0  # seconds in OPEN before attempting recovery

    _state: CBState = field(default=CBState.CLOSED, init=False, repr=False)
    _failure_count: int = field(default=0, init=False, repr=False)
    _last_failure_at: float = field(default=0.0, init=False, repr=False)

    @property
    def state(self) -> CBState:
        """Current state, auto-advancing OPEN → HALF_OPEN after recovery_timeout."""
        if self._state is CBState.OPEN:
            if time.monotonic() - self._last_failure_at >= self.recovery_timeout:
                self._state = CBState.HALF_OPEN
                logger.info("Circuit breaker %s → HALF_OPEN (probing recovery)", self.name)
        return self._state

    @property
    def is_open(self) -> bool:
        return self.state is CBState.OPEN

    def allow_request(self) -> bool:
        """Return True if the provider should be called; False to skip immediately."""
        allowed = self.state is not CBState.OPEN
        if not allowed:
            logger.debug(
                "Circuit breaker %s is OPEN — skipping provider (%.0fs until half-open)",
                self.name,
                max(0, self.recovery_timeout - (time.monotonic() - self._last_failure_at)),
            )
        return allowed

    def record_success(self) -> None:
        """Called after a successful provider response."""
        prev = self._state
        self._failure_count = 0
        self._state = CBState.CLOSED
        if prev is not CBState.CLOSED:
            logger.info("Circuit breaker %s → CLOSED (recovered)", self.name)

    def record_failure(self) -> None:
        """Called after any provider error or timeout."""
        self._failure_count += 1
        self._last_failure_at = time.monotonic()
        if self._state is CBState.HALF_OPEN or self._failure_count >= self.failure_threshold:
            prev_count = self._failure_count
            self._failure_count = 0
            self._state = CBState.OPEN
            logger.warning(
                "Circuit breaker %s → OPEN (failures=%d, threshold=%d)",
                self.name, prev_count, self.failure_threshold,
            )


# Global registry — one breaker per provider name
_registry: dict[str, CircuitBreaker] = {}


def get_breaker(provider_name: str) -> CircuitBreaker:
    """Return the singleton CircuitBreaker for a provider, creating it if needed."""
    if provider_name not in _registry:
        _registry[provider_name] = CircuitBreaker(name=provider_name)
    return _registry[provider_name]


def all_breakers() -> dict[str, CircuitBreaker]:
    """Return a snapshot of all registered circuit breakers (for metrics export)."""
    return dict(_registry)
