"""WebSocket connection manager for real-time pipeline progress streaming.

One WebSocket per query_id can connect and receive JSON events as the pipeline
executes. Multiple clients watching the same query_id are all supported.
Events are also published when a client connects *after* the run is done
(fetched from the DB log) so late joiners see the full history.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # query_id → list of active WebSocket connections
        self._active: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, query_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._active[query_id].append(ws)
        logger.debug("WS connected: query=%s  total=%d", query_id, len(self._active[query_id]))

    def disconnect(self, query_id: str, ws: WebSocket) -> None:
        sockets = self._active.get(query_id, [])
        if ws in sockets:
            sockets.remove(ws)
        logger.debug("WS disconnected: query=%s  remaining=%d", query_id, len(sockets))

    async def broadcast(self, query_id: str, payload: dict[str, Any]) -> None:
        """Send a JSON event to all clients watching this query."""
        dead: list[WebSocket] = []
        for ws in list(self._active.get(query_id, [])):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(query_id, ws)

    def is_anyone_watching(self, query_id: str) -> bool:
        return bool(self._active.get(query_id))


# Module-level singleton — imported by route handlers and the pipeline runner
ws_manager = ConnectionManager()


async def ws_endpoint(
    query_id: str,
    websocket: WebSocket,
    api_key: str | None = None,
) -> None:
    """WebSocket endpoint handler. Attach to a FastAPI route via APIRouter."""
    from researchhq.api import db
    from researchhq.api.auth import ws_validate

    if not await ws_validate(websocket, api_key):
        return

    await ws_manager.connect(query_id, websocket)
    try:
        # Replay recent logs so a late-joining client sees context
        logs = db.get_logs(query_id, limit=50)
        for log in logs:
            await websocket.send_text(json.dumps({
                "event": "log_replay",
                "stage": log.get("stage", ""),
                "message": log.get("message", ""),
                "level": log.get("level", "info"),
                "data": log.get("data"),
                "timestamp": log.get("created_at"),
            }))

        # Keep connection alive — client will disconnect when it no longer needs events
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                # Send a keepalive ping
                await websocket.send_text(json.dumps({"event": "ping"}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("WebSocket closed unexpectedly for query=%s: %s", query_id, e)
    finally:
        ws_manager.disconnect(query_id, websocket)
