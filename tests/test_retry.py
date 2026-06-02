from __future__ import annotations

import asyncio
import time

import pytest

from researchhq.utils.retry import with_retry


def test_retry_timeout_is_wall_time_not_per_attempt() -> None:
    calls = 0

    async def slow() -> None:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.04)
        raise ConnectionError("temporary")

    started = time.monotonic()
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(with_retry(slow, attempts=3, timeout=0.07, base_delay=0.05, label="slow"))

    assert calls <= 2
    assert time.monotonic() - started < 0.18
