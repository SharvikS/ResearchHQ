"""GET /api/v1/logs/{query_id} — retrieve structured execution logs for a query."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from researchhq.api import db
from researchhq.api.schemas import LogEntry, LogsResponse

router = APIRouter(prefix="/api/v1", tags=["logs"])


def _parse_dt(s: Optional[str]) -> datetime:
    if not s:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.now(timezone.utc)


@router.get("/logs/{query_id}", response_model=LogsResponse)
async def get_logs(
    query_id: str,
    level: Optional[str] = Query(None, description="Filter by log level: debug|info|warn|error"),
    stage: Optional[str] = Query(None, description="Filter by pipeline stage"),
    limit: int = Query(200, ge=1, le=1000),
) -> LogsResponse:
    """Return structured execution logs for a query, with optional filters."""
    row = db.get_query(query_id)
    if not row:
        raise HTTPException(404, detail=f"Query {query_id!r} not found.")

    raw_logs = db.get_logs(query_id, level=level, stage=stage, limit=limit)
    entries = [
        LogEntry(
            id=log["id"],
            query_id=query_id,
            level=log.get("level", "info"),
            stage=log.get("stage", ""),
            message=log.get("message", ""),
            data=log.get("data"),
            created_at=_parse_dt(log.get("created_at")),
        )
        for log in raw_logs
    ]

    return LogsResponse(query_id=query_id, logs=entries, total=len(entries))
