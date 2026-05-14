"""Background pipeline runner for the API layer.

Bridges researchhq.pipeline.run() → DB persistence + WebSocket broadcasting.
Each query runs as an asyncio Task. Events emitted by the pipeline are:
  1. Stored as structured logs in SQLite
  2. Broadcast in real-time to any WebSocket clients watching the query

The final ResearchReport is converted to the API FinalResponse schema and
stored in the query_results table.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from researchhq.api import db
from researchhq.api.ws import ws_manager
from researchhq.events import PipelineEvent

logger = logging.getLogger(__name__)

# Active query tasks: query_id → asyncio.Task
_running: dict[str, asyncio.Task] = {}


def is_running(query_id: str) -> bool:
    task = _running.get(query_id)
    return task is not None and not task.done()


async def _broadcast_and_log(
    query_id: str,
    event: PipelineEvent,
) -> None:
    """Store event as a DB log entry and push to WebSocket clients."""
    level = "error" if event.type in ("run_failed", "agent_failed") else "info"
    db.append_log(
        query_id=query_id,
        level=level,
        stage=event.stage,
        message=event.detail or event.type,
        data={k: v for k, v in event.data.items() if k not in ("body", "raw")},
    )

    payload: dict[str, Any] = {
        "event": event.type,
        "stage": event.stage,
        "detail": event.detail,
        **{k: v for k, v in event.data.items()
           if isinstance(v, (str, int, float, bool, list, dict, type(None)))},
    }
    await ws_manager.broadcast(query_id, payload)


def _report_to_result_data(report: Any, query_id: str) -> dict:
    """Convert a ResearchReport into the flat dict we store in query_results."""
    from researchhq.llm.cost_tracker import tracker

    # Build executive summary from first section body (first 500 chars)
    first_section = report.sections[0] if report.sections else None
    exec_summary = (first_section.body[:500] if first_section else "") or ""

    # Full answer: concatenate all sections
    detailed = "\n\n".join(
        f"## {s.heading}\n\n{s.body}" for s in report.sections
    ) if report.sections else ""

    # Key findings from verifier rule failures + unique facts
    key_findings: list[str] = []
    for fact in (report.facts or [])[:10]:
        text = getattr(fact, "text", str(fact))
        if text and text not in key_findings:
            key_findings.append(text.strip())

    # Sources
    sources = []
    for src in (report.sources or []):
        sources.append({
            "url": getattr(src, "url", ""),
            "title": getattr(src, "title", ""),
            "domain": getattr(src, "domain", ""),
            "trust_score": float(getattr(src, "tier_score", 0.5)),
            "snippet": getattr(src, "snippet", None),
        })

    # Confidence
    ensemble = getattr(report, "ensemble", None)
    if ensemble:
        conf_score = getattr(ensemble, "adjusted_confidence", 0.5)
        conf_label = (
            "high" if conf_score >= 0.75
            else "medium" if conf_score >= 0.50
            else "low"
        )
        conf_breakdown = {
            "provider_agreement": getattr(ensemble, "provider_agreement_score", 0.0),
            "source_quality": getattr(ensemble, "source_quality_score", 0.0),
            "factual_consistency": getattr(ensemble, "factual_consistency_score", 0.0),
            "hallucination_safety": 1.0 - getattr(ensemble, "hallucination_risk", 0.5),
        }
        limitations: list[str] = list(getattr(ensemble, "uncertainty_notes", []))
    else:
        verifier = getattr(report, "verifier", None)
        conf_score = float(getattr(verifier, "overall_confidence", 0.5) if verifier else 0.5)
        conf_label = "high" if conf_score >= 0.75 else "medium" if conf_score >= 0.5 else "low"
        conf_breakdown = {"provider_agreement": conf_score, "source_quality": conf_score,
                          "factual_consistency": conf_score, "hallucination_safety": conf_score}
        limitations = []

    # Execution metadata
    stage_costs = getattr(report, "stage_costs", [])
    total_in = sum(getattr(sc, "input_tokens", 0) for sc in stage_costs)
    total_out = sum(getattr(sc, "output_tokens", 0) for sc in stage_costs)
    total_cost = sum(getattr(sc, "equivalent_cost_usd", 0.0) for sc in stage_costs)

    return {
        "executive_summary": exec_summary,
        "detailed_answer": detailed,
        "key_findings": key_findings,
        "conflicting_viewpoints": [],
        "limitations": limitations,
        "confidence_score": conf_score,
        "confidence_label": conf_label,
        "confidence_breakdown": conf_breakdown,
        "sources": sources,
        "agent_outputs": {},
        "execution_metadata": {
            "pipelines_run": len(getattr(report, "sections", [])),
            "pipelines_failed": 0,
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "estimated_cost_usd": total_cost,
            "ensemble_mode": getattr(report, "ensemble", {}) and getattr(
                getattr(report, "ensemble", None), "ensemble_mode", "balanced"
            ) or "balanced",
            "provider_used": getattr(report, "provider_used", "unknown"),
        },
    }


async def run_query(
    query_id: str,
    query: str,
    mode: str,
    pipeline_mode: str,
    ensemble_mode: str,
) -> None:
    """Execute the full research pipeline for a query and persist the result."""
    import researchhq.pipeline as pipeline_mod
    from researchhq.config import settings as cfg

    db.update_query_status(query_id, "running")
    await ws_manager.broadcast(query_id, {"event": "run_started", "query": query})

    # Override ensemble settings for this run
    original_ensemble_enabled = cfg.ensemble_enabled
    original_ensemble_mode = cfg.ensemble_mode
    cfg.ensemble_enabled = True
    cfg.ensemble_mode = ensemble_mode

    def _on_event(ev: PipelineEvent) -> None:
        asyncio.create_task(_broadcast_and_log(query_id, ev))

        # Mirror pipeline_stage updates to the DB for the /status endpoint
        if ev.type == "agent_started":
            slot = ev.stage
            db.upsert_pipeline_stage(
                query_id=query_id, slot_name=slot,
                display_name=slot.replace("_", " ").title(),
                provider=str(ev.data.get("providers", ["unknown"])[0])
                         if ev.data.get("providers") else "unknown",
                status="running",
            )
        elif ev.type == "agent_finished":
            slot = ev.stage
            latency = int(ev.data.get("elapsed", 0) * 1000) if ev.data.get("elapsed") else None
            db.upsert_pipeline_stage(
                query_id=query_id, slot_name=slot,
                display_name=slot.replace("_", " ").title(),
                provider=str(ev.data.get("provider_label", "unknown")),
                status="complete",
                latency_ms=latency,
            )
        elif ev.type == "agent_failed":
            slot = ev.stage
            db.upsert_pipeline_stage(
                query_id=query_id, slot_name=slot,
                display_name=slot.replace("_", " ").title(),
                provider="unknown",
                status="failed",
                error=ev.detail,
            )

    try:
        report = await pipeline_mod.run(
            mode_name=mode,
            query=query,
            on_event=_on_event,
            effort=_pipeline_mode_to_effort(pipeline_mode),
        )

        result_data = _report_to_result_data(report, query_id)
        db.save_result(query_id, result_data)
        db.update_query_status(query_id, "complete")

        await ws_manager.broadcast(query_id, {
            "event": "result_ready",
            "query_id": query_id,
            "confidence": result_data["confidence_score"],
            "label": result_data["confidence_label"],
        })

    except asyncio.CancelledError:
        db.update_query_status(query_id, "failed", error="Query was cancelled.")
        await ws_manager.broadcast(query_id, {"event": "run_canceled", "query_id": query_id})
        raise

    except Exception as e:
        logger.exception("Pipeline failed for query %s", query_id)
        db.update_query_status(query_id, "failed", error=str(e))
        await ws_manager.broadcast(query_id, {
            "event": "run_failed",
            "query_id": query_id,
            "error": str(e),
        })

    finally:
        # Restore ensemble settings (settings object is a global singleton)
        cfg.ensemble_enabled = original_ensemble_enabled
        cfg.ensemble_mode = original_ensemble_mode
        _running.pop(query_id, None)


def _pipeline_mode_to_effort(pipeline_mode: str) -> str:
    return {"fast": "low", "balanced": "medium", "deep": "high"}.get(pipeline_mode, "medium")


def start_query(
    query_id: str,
    query: str,
    mode: str,
    pipeline_mode: str,
    ensemble_mode: str,
) -> None:
    """Launch the pipeline as an asyncio background task."""
    task = asyncio.create_task(
        run_query(query_id, query, mode, pipeline_mode, ensemble_mode),
        name=f"query-{query_id}",
    )
    _running[query_id] = task
    logger.info("Started pipeline task for query %s", query_id)
