"""Async retry + timeout helper. Used by search and LLM call paths.

Design:
- Treat asyncio.TimeoutError, ConnectionError, and explicit transient HTTP errors as retryable.
- Treat ValueError, KeyError, and authentication failures as permanent (do not retry).
- Exponential backoff with jitter cap; hard upper bound on total wall time."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# Default classifier — overrideable per call.
_PERMANENT = (ValueError, KeyError, TypeError, AttributeError)


def is_retryable(err: BaseException) -> bool:
    if isinstance(err, _PERMANENT):
        return False
    msg = str(err).lower()
    # Auth failures should not be retried.
    if any(t in msg for t in ("invalid api key", "unauthorized", "401", "403", "permission denied")):
        return False
    return True


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 4.0,
    timeout: float | None = None,
    label: str = "op",
    classify: Callable[[BaseException], bool] = is_retryable,
) -> T:
    """Run `fn()` with retry + a hard wall-time timeout.

    When ``timeout`` is provided, the whole retry operation is bounded by that
    value. Each attempt receives only the remaining budget, so retries cannot
    silently multiply the documented timeout.
    """
    last: BaseException | None = None
    deadline = None if timeout is None else time.monotonic() + timeout
    for i in range(1, attempts + 1):
        try:
            if timeout is None:
                return await fn()
            remaining = deadline - time.monotonic() if deadline is not None else timeout
            if remaining <= 0:
                raise TimeoutError(f"{label} timed out after {timeout:.1f}s")
            return await asyncio.wait_for(fn(), timeout=remaining)
        except asyncio.CancelledError:
            raise
        except BaseException as e:  # noqa: BLE001 — intentional broad catch
            last = e
            if not classify(e) or i == attempts:
                logger.debug("%s: not retrying (%s)", label, type(e).__name__)
                raise
            sleep = min(max_delay, base_delay * (2 ** (i - 1)))
            sleep = sleep * (0.5 + random.random())  # jitter 0.5x..1.5x
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"{label} timed out after {timeout:.1f}s") from e
                sleep = min(sleep, remaining)
            logger.info("%s: attempt %d/%d failed (%s); retrying in %.2fs",
                        label, i, attempts, type(e).__name__, sleep)
            await asyncio.sleep(sleep)
    # Unreachable, but keeps type checker happy.
    assert last is not None
    raise last
