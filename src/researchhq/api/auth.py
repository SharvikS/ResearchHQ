"""API key authentication and per-key sliding-window rate limiting.

Auth is opt-in via environment variables so local dev works without config:

  RHQ_REQUIRE_AUTH=true      — enforce API key on all /api/v1/* routes + WebSocket
  RHQ_API_KEYS=key1,key2     — comma-separated list of valid keys
  RHQ_RATE_LIMIT_RPM=60      — max requests per minute per key (0 = unlimited)

If RHQ_REQUIRE_AUTH=true but RHQ_API_KEYS is empty, a random ephemeral key is
generated at startup and printed to the log — useful for one-shot deploys.

Usage in REST routes:
    from researchhq.api.auth import require_auth
    @router.get("/something")
    async def handler(_: str = Depends(require_auth)) -> ...:

WebSocket: pass ?api_key=<key> query parameter.
    from researchhq.api.auth import ws_validate
    if not await ws_validate(websocket, api_key):
        return  # socket already closed
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from collections import deque
from typing import Optional

from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _load_config() -> tuple[bool, set[str], int]:
    require = os.environ.get("RHQ_REQUIRE_AUTH", "").lower() in ("1", "true", "yes")
    raw = os.environ.get("RHQ_API_KEYS", "")
    keys: set[str] = {k.strip() for k in raw.split(",") if k.strip()}
    rpm = max(0, int(os.environ.get("RHQ_RATE_LIMIT_RPM", "60")))
    return require, keys, rpm


_REQUIRE_AUTH, _VALID_KEYS, _RATE_LIMIT_RPM = _load_config()

if _REQUIRE_AUTH and not _VALID_KEYS:
    _ephemeral = "rhq_" + secrets.token_urlsafe(32)
    _VALID_KEYS = {_ephemeral}
    logger.warning(
        "RHQ_REQUIRE_AUTH=true but RHQ_API_KEYS is not set. "
        "Generated ephemeral API key (valid for this process only): %s",
        _ephemeral,
    )

# In-memory sliding window per key: key → deque of monotonic timestamps
_windows: dict[str, deque] = {}


def _check_rate_limit(key: str) -> None:
    """Sliding-window rate check. Raises HTTP 429 if the key exceeds the limit."""
    if _RATE_LIMIT_RPM <= 0:
        return
    now = time.monotonic()
    q = _windows.setdefault(key, deque())
    cutoff = now - 60.0
    while q and q[0] < cutoff:
        q.popleft()
    if len(q) >= _RATE_LIMIT_RPM:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({_RATE_LIMIT_RPM} req/min). Retry after 60 s.",
            headers={"Retry-After": "60"},
        )
    q.append(now)


def _validate_key(key: Optional[str]) -> str:
    """Core validation logic shared by REST and WebSocket paths."""
    if not _REQUIRE_AUTH:
        effective = key or "__anon__"
        _check_rate_limit(effective)
        return effective

    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide it via the X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if key not in _VALID_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )
    _check_rate_limit(key)
    return key


async def require_auth(
    api_key: Optional[str] = Depends(_KEY_HEADER),
) -> str:
    """FastAPI dependency — validates X-API-Key header and enforces rate limit.

    Add to any route that should be protected:
        async def handler(_: str = Depends(require_auth)) -> ...:
    """
    return _validate_key(api_key)


async def ws_validate(websocket: WebSocket, api_key: Optional[str]) -> bool:
    """Validate a WebSocket connection before accepting it.

    Returns True if the connection should proceed.
    On failure: closes the socket with code 1008 (policy violation) and returns False.
    """
    if not _REQUIRE_AUTH:
        if _RATE_LIMIT_RPM > 0:
            try:
                _check_rate_limit(api_key or "__anon__")
            except HTTPException:
                await websocket.close(code=1008)
                return False
        return True

    if not api_key or api_key not in _VALID_KEYS:
        await websocket.close(code=1008)
        return False

    try:
        _check_rate_limit(api_key)
    except HTTPException:
        await websocket.close(code=1008)
        return False

    return True
