"""Query endpoints: POST /query, GET /query/{id}/status, GET /query/{id}/result."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from researchhq.api import db, runner
from researchhq.api.auth import require_auth
from researchhq.api.schemas import (
    ConfidenceBreakdown,
    ConfidenceResult,
    ExecutionMetadata,
    FinalResponse,
    PipelineStatus,
    QueryRequest,
    QueryResultResponse,
    QueryStatusResponse,
    SourceRef,
)
from researchhq.security.sanitizer import sanitize_query

router = APIRouter(prefix="/api/v1", tags=["queries"])


def _parse_dt(s: Optional[str]) -> datetime:
    if not s:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.now(timezone.utc)


@router.post("/query", status_code=202)
async def submit_query(body: QueryRequest, _: str = Depends(require_auth)) -> dict:
    """Submit a new research query. Returns a query_id for polling or WebSocket."""
    cleaned, warnings = sanitize_query(body.query)
    if not cleaned:
        raise HTTPException(400, detail="Query is empty after sanitization.")

    query_id = "q_" + uuid.uuid4().hex[:12]

    db.create_query(
        query_id=query_id,
        raw_query=cleaned,
        mode=body.mode,
        pipeline_mode=body.pipeline_mode,
        fmt=body.format,
    )

    # Log any sanitization warnings
    for w in warnings:
        db.append_log(query_id, "warn", "security", w)

    runner.start_query(
        query_id=query_id,
        query=cleaned,
        mode=body.mode,
        pipeline_mode=body.pipeline_mode,
        ensemble_mode=body.options.ensemble_mode,
    )

    effort_map = {"fast": 15, "balanced": 45, "deep": 120}
    estimated = effort_map.get(body.pipeline_mode, 45)

    return {
        "query_id": query_id,
        "status": "queued",
        "estimated_completion_s": estimated,
        "websocket_url": f"/ws/{query_id}",
        "poll_url": f"/api/v1/query/{query_id}/status",
        "warnings": warnings,
    }


@router.get("/query/{query_id}/status", response_model=QueryStatusResponse)
async def get_query_status(query_id: str, _: str = Depends(require_auth)) -> QueryStatusResponse:
    """Poll execution status and per-pipeline progress."""
    row = db.get_query(query_id)
    if not row:
        raise HTTPException(404, detail=f"Query {query_id!r} not found.")

    stages = db.get_pipeline_stages(query_id)
    pipelines = [
        PipelineStatus(
            slot_name=s["slot_name"],
            display_name=s.get("display_name") or s["slot_name"],
            provider=s.get("provider") or "unknown",
            status=s["status"],
            latency_ms=s.get("latency_ms"),
            error=s.get("error"),
        )
        for s in stages
    ]

    # Rough progress: fraction of stages completed
    done = sum(1 for p in pipelines if p.status in ("complete", "failed", "timeout"))
    total = max(len(pipelines), 1)
    progress = int((done / total) * 80)  # reserve last 20% for synthesis
    if row["status"] == "complete":
        progress = 100
    elif row["status"] == "failed":
        progress = 100

    return QueryStatusResponse(
        query_id=query_id,
        status=row["status"],
        progress_pct=progress,
        pipelines=pipelines,
        created_at=_parse_dt(row.get("created_at")),
        updated_at=_parse_dt(row.get("updated_at")),
        error=row.get("error"),
    )


@router.get("/query/{query_id}/result", response_model=QueryResultResponse)
async def get_query_result(query_id: str, _: str = Depends(require_auth)) -> QueryResultResponse:
    """Retrieve the complete final response. Returns 202 body if still running."""
    row = db.get_query(query_id)
    if not row:
        raise HTTPException(404, detail=f"Query {query_id!r} not found.")

    if row["status"] in ("queued", "running"):
        return QueryResultResponse(
            query_id=query_id,
            status=row["status"],
            warnings=["Query is still processing — poll /status or use WebSocket."],
        )

    if row["status"] == "failed":
        return QueryResultResponse(
            query_id=query_id,
            status="failed",
            warnings=[row.get("error") or "Pipeline failed."],
        )

    result = db.get_result(query_id)
    if not result:
        raise HTTPException(500, detail="Result record missing despite complete status.")

    # Build typed response
    bd = result.get("confidence_detail") or {}
    conf = ConfidenceResult(
        overall_score=result.get("confidence_score", 0.0),
        label=result.get("confidence_label", "low"),
        breakdown=ConfidenceBreakdown(
            provider_agreement=bd.get("provider_agreement", 0.0),
            source_quality=bd.get("source_quality", 0.0),
            factual_consistency=bd.get("factual_consistency", 0.0),
            hallucination_safety=bd.get("hallucination_safety", 0.0),
        ),
        uncertainty_notes=[],
    )

    meta_raw = result.get("execution_metadata") or {}
    meta = ExecutionMetadata(
        total_latency_ms=meta_raw.get("total_latency_ms", 0),
        pipelines_run=meta_raw.get("pipelines_run", 0),
        pipelines_failed=meta_raw.get("pipelines_failed", 0),
        total_input_tokens=meta_raw.get("total_input_tokens", 0),
        total_output_tokens=meta_raw.get("total_output_tokens", 0),
        estimated_cost_usd=meta_raw.get("estimated_cost_usd", 0.0),
        ensemble_mode=meta_raw.get("ensemble_mode", "balanced"),
        provider_used=meta_raw.get("provider_used", "unknown"),
    )

    sources = [
        SourceRef(
            url=s.get("url", ""),
            title=s.get("title", ""),
            domain=s.get("domain", ""),
            trust_score=s.get("trust_score", 0.3),
            snippet=s.get("snippet"),
        )
        for s in (result.get("sources") or [])
    ]

    final = FinalResponse(
        query_id=query_id,
        status=row["status"],
        executive_summary=result.get("executive_summary", ""),
        detailed_answer=result.get("detailed_answer", ""),
        key_findings=result.get("key_findings") or [],
        conflicting_viewpoints=result.get("conflicting_views") or [],
        limitations=result.get("limitations") or [],
        confidence=conf,
        sources=sources,
        agent_outputs={},
        execution_metadata=meta,
        created_at=_parse_dt(result.get("created_at")),
    )

    return QueryResultResponse(
        query_id=query_id,
        status=row["status"],
        final_response=final,
    )
