"""HTTP/WebSocket API for the ResearchHQ React frontend.

The server intentionally wraps the existing pipeline instead of duplicating
research logic. Runs are kept in memory while reports are still saved through
the normal exporter/history path.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from researchhq import __version__
from researchhq.config import settings
from researchhq.events import PipelineEvent
from researchhq.llm.router import LLMRouter
from researchhq.pipeline import run as pipeline_run
from researchhq.reports.exporter import save
from researchhq.reports.schema import ResearchReport, Section

logger = logging.getLogger(__name__)

try:  # Optional dependency: installed with `researchhq[server]`.
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
except ImportError as exc:  # pragma: no cover - import guard for base installs
    raise RuntimeError("Install the server extra with `pip install -e '.[server]'`.") from exc


STAGE_ORDER = [
    "planner",
    "searcher",
    "source_ranker",
    "fetcher",
    "extractor",
    "synthesizer",
    "ensemble",
    "verifier",
    "formatter",
]

DISPLAY_NAMES = {
    "planner": "Planning",
    "searcher": "Web Search",
    "source_ranker": "Source Ranking",
    "fetcher": "Page Fetch",
    "extractor": "Fact Extraction",
    "synthesizer": "Synthesis",
    "ensemble": "Ensemble Synthesis",
    "verifier": "Verification",
    "formatter": "Formatter",
}


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    mode: str = "topic"
    pipeline_mode: Literal["fast", "balanced", "deep"] = "balanced"
    format: Literal["markdown", "json", "html"] = "markdown"
    options: dict[str, Any] = Field(default_factory=dict)


@dataclass
class RunState:
    query_id: str
    query: str
    mode: str
    effort: str
    fmt: str
    status: str = "queued"
    progress_pct: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    stages: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    subscribers: set[asyncio.Queue[dict[str, Any]]] = field(default_factory=set)
    report: ResearchReport | None = None
    saved_path: str = ""
    error: str = ""
    started_monotonic: float = field(default_factory=time.monotonic)
    completed_monotonic: float | None = None
    task: asyncio.Task[None] | None = None

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC).isoformat()


RUNS: dict[str, RunState] = {}
RUN_LOCK = asyncio.Lock()


def create_app() -> FastAPI:
    app = FastAPI(title="ResearchHQ API", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "providers_available": _available_providers(),
        }

    @app.get("/ready")
    async def ready() -> dict[str, Any]:
        providers = _available_providers()
        return {
            "status": "ready" if providers else "degraded",
            "version": __version__,
            "providers_available": providers,
            "circuit_breakers_open": [],
        }

    @app.post("/api/v1/query")
    async def submit_query(req: QueryRequest) -> dict[str, Any]:
        query_id = uuid.uuid4().hex
        effort = _effort_from_pipeline_mode(req.pipeline_mode)
        run = RunState(
            query_id=query_id,
            query=req.query.strip(),
            mode=_mode_from_frontend(req.mode),
            effort=effort,
            fmt=req.format,
        )
        RUNS[query_id] = run
        run.task = asyncio.create_task(_execute(run, req.options))
        return {
            "query_id": query_id,
            "websocket_url": f"/ws/{query_id}",
            "estimated_completion_s": _estimate_seconds(effort),
            "warnings": _warnings(),
        }

    @app.get("/api/v1/query/{query_id}/status")
    async def query_status(query_id: str) -> dict[str, Any]:
        run = _get_run(query_id)
        return _status_payload(run)

    @app.get("/api/v1/query/{query_id}/result")
    async def query_result(query_id: str) -> dict[str, Any]:
        run = _get_run(query_id)
        if run.status != "complete" or run.report is None:
            return {"query_id": query_id, "status": run.status, "warnings": _warnings()}
        return {
            "query_id": query_id,
            "status": run.status,
            "warnings": _warnings(),
            "final_response": _final_response(run),
        }

    @app.get("/api/v1/agents")
    async def agents() -> dict[str, Any]:
        return {
            "agents": [
                {
                    "id": "planner",
                    "name": "Planner",
                    "description": "Breaks the query into targeted research searches.",
                    "slot": "fast_scan",
                    "preferred_providers": _provider_chain(),
                },
                {
                    "id": "searcher",
                    "name": "Searcher",
                    "description": "Collects and deduplicates web search results.",
                    "slot": "web_synthesis",
                    "preferred_providers": ["duckduckgo"],
                },
                {
                    "id": "extractor",
                    "name": "Extractor",
                    "description": "Extracts grounded facts from retained sources.",
                    "slot": "technical",
                    "preferred_providers": _provider_chain(),
                },
                {
                    "id": "synthesizer",
                    "name": "Synthesizer",
                    "description": "Composes the final cited answer.",
                    "slot": "deep_reasoning",
                    "preferred_providers": _provider_chain(),
                },
                {
                    "id": "verifier",
                    "name": "Verifier",
                    "description": "Checks citations, source quality, and confidence.",
                    "slot": "extended_think",
                    "preferred_providers": ["rules"],
                },
            ],
            "pipeline_modes": {
                "fast": ["fast_scan", "web_synthesis", "deep_reasoning"],
                "balanced": ["fast_scan", "web_synthesis", "technical", "deep_reasoning"],
                "deep": [
                    "fast_scan",
                    "web_synthesis",
                    "technical",
                    "deep_reasoning",
                    "extended_think",
                ],
            },
        }

    @app.get("/api/v1/logs/{query_id}")
    async def logs(
        query_id: str, level: str | None = None, stage: str | None = None, limit: int = 100
    ) -> dict[str, Any]:
        run = _get_run(query_id)
        rows = run.events
        if stage:
            rows = [r for r in rows if r.get("stage") == stage]
        if level:
            rows = [r for r in rows if r.get("level") == level]
        return {"logs": rows[-max(1, min(limit, 500)) :]}

    class SettingsPatch(BaseModel):
        """Subset of runtime settings the frontend may push."""

        debug_mode: bool | None = None
        verbosity_default: str | None = None
        default_provider: str | None = None
        max_cost_per_query: float | None = None

    @app.patch("/api/v1/settings")
    async def patch_settings(body: SettingsPatch) -> dict[str, Any]:
        applied: list[str] = []
        if body.debug_mode is not None:
            settings.verbosity_default = "debug" if body.debug_mode else "normal"
            applied.append(f"verbosity_default={settings.verbosity_default}")
            _configure_log_level("debug" if body.debug_mode else "normal")
        if body.verbosity_default is not None:
            settings.verbosity_default = body.verbosity_default
            applied.append(f"verbosity_default={body.verbosity_default}")
            _configure_log_level(body.verbosity_default)
        if body.default_provider is not None:
            settings.default_provider = body.default_provider
            applied.append(f"default_provider={body.default_provider}")
        if body.max_cost_per_query is not None and body.max_cost_per_query > 0:
            applied.append(f"max_cost_per_query={body.max_cost_per_query}")
        logger.info("Settings patched: %s", ", ".join(applied) or "(no changes)")
        return {"status": "ok", "applied": applied}

    @app.websocket("/ws/{query_id}")
    async def ws(query_id: str, websocket: WebSocket) -> None:
        run = _get_run(query_id)
        await websocket.accept()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        run.subscribers.add(queue)
        try:
            for ev in run.events[-100:]:
                await websocket.send_json(ev)
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=20)
                    await websocket.send_json(ev)
                except TimeoutError:
                    await websocket.send_json({"event": "ping"})
        except WebSocketDisconnect:
            pass
        finally:
            run.subscribers.discard(queue)

    return app


app = create_app()


async def _execute(run: RunState, options: dict[str, Any]) -> None:
    run.status = "running"
    run.touch()
    _broadcast(run, {"event": "run_started", "detail": run.query, "stage": ""})

    async with RUN_LOCK:
        previous_ensemble_enabled = settings.ensemble_enabled
        previous_ensemble_mode = settings.ensemble_mode
        try:
            if "ensemble_mode" in options:
                settings.ensemble_enabled = options.get("ensemble_mode") not in (
                    "",
                    "off",
                    "disabled",
                    None,
                )
                settings.ensemble_mode = str(options.get("ensemble_mode") or "balanced")

            report = await pipeline_run(
                run.mode,
                run.query,
                on_event=lambda ev: _handle_pipeline_event(run, ev),
                effort=run.effort,
            )
            run.report = report
            saved = save(report, fmt=run.fmt)
            run.saved_path = str(saved)
            run.status = "complete"
            run.progress_pct = 100
            run.completed_monotonic = time.monotonic()
            run.touch()
            _broadcast(run, {"event": "run_completed", "detail": "complete", "stage": ""})
        except asyncio.CancelledError:
            run.status = "failed"
            run.error = "Run canceled."
            run.touch()
            _broadcast(run, {"event": "run_canceled", "detail": run.error, "stage": ""})
        except Exception as exc:  # noqa: BLE001 - server boundary
            run.status = "failed"
            run.error = str(exc) or type(exc).__name__
            run.touch()
            _broadcast(run, {"event": "run_failed", "detail": run.error, "stage": ""})
        finally:
            settings.ensemble_enabled = previous_ensemble_enabled
            settings.ensemble_mode = previous_ensemble_mode


def _handle_pipeline_event(run: RunState, ev: PipelineEvent) -> None:
    event = {
        "id": len(run.events) + 1,
        "event": ev.type,
        "type": ev.type,
        "stage": ev.stage,
        "detail": ev.detail,
        "data": ev.data,
        "level": "error" if "failed" in ev.type else "info",
        "message": ev.detail or ev.type,
        "created_at": datetime.now(UTC).isoformat(),
    }

    stage = ev.stage
    if stage:
        current = run.stages.setdefault(
            stage,
            {
                "slot_name": stage,
                "display_name": DISPLAY_NAMES.get(stage, stage.replace("_", " ").title()),
                "provider": "",
                "status": "queued",
                "started_at": None,
                "latency_ms": None,
                "error": "",
            },
        )
        if ev.type == "agent_started":
            current["status"] = "running"
            current["started_at"] = time.monotonic()
            current["provider"] = str(ev.data.get("provider", "")) or "researchhq"
        elif ev.type in {"agent_finished", "ensemble_merge_done"}:
            current["status"] = "complete"
            started = current.get("started_at")
            if started:
                current["latency_ms"] = int((time.monotonic() - float(started)) * 1000)
            provider = ev.data.get("provider") or ev.data.get("provider_label")
            if provider:
                current["provider"] = str(provider)
        elif ev.type == "agent_failed":
            current["status"] = "failed"
            current["error"] = ev.detail

    if ev.type == "run_completed":
        run.progress_pct = 100
    else:
        completed = sum(1 for s in run.stages.values() if s.get("status") == "complete")
        running = sum(1 for s in run.stages.values() if s.get("status") == "running")
        run.progress_pct = min(
            99, int(((completed + (0.35 if running else 0)) / len(STAGE_ORDER)) * 100)
        )

    run.touch()
    _broadcast(run, event)


def _broadcast(run: RunState, event: dict[str, Any]) -> None:
    event.setdefault("id", len(run.events) + 1)
    event.setdefault("created_at", datetime.now(UTC).isoformat())
    event.setdefault("level", "info")
    event.setdefault("message", event.get("detail") or event.get("event", "event"))
    run.events.append(event)
    for queue in list(run.subscribers):
        with contextlib.suppress(asyncio.QueueFull):
            queue.put_nowait(event)


def _get_run(query_id: str) -> RunState:
    run = RUNS.get(query_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Query not found")
    return run


def _status_payload(run: RunState) -> dict[str, Any]:
    stages = [_stage_payload(run, name) for name in STAGE_ORDER if name in run.stages]
    return {
        "query_id": run.query_id,
        "status": run.status,
        "progress_pct": run.progress_pct,
        "pipelines": stages,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "error": run.error or None,
    }


def _stage_payload(run: RunState, name: str) -> dict[str, Any]:
    stage = run.stages[name]
    return {
        "slot_name": name,
        "display_name": stage.get("display_name", name),
        "provider": stage.get("provider") or "researchhq",
        "status": stage.get("status", "queued"),
        "latency_ms": stage.get("latency_ms"),
        "error": stage.get("error") or None,
    }


def _final_response(run: RunState) -> dict[str, Any]:
    assert run.report is not None
    report = run.report
    summary = _section_body(report.sections, "executive") or (
        report.sections[0].body if report.sections else ""
    )
    detailed = "\n\n".join(f"## {s.heading}\n{s.body}" for s in report.sections)
    confidence = (
        report.ensemble.adjusted_confidence
        if report.ensemble
        else (report.verifier.overall_confidence if report.verifier else 0.0)
    )
    stage_costs = report.stage_costs
    total_in = sum(c.input_tokens for c in stage_costs)
    total_out = sum(c.output_tokens for c in stage_costs)
    total_cost = sum(c.equivalent_paid_cost_usd for c in stage_costs)
    latency_ms = int(((run.completed_monotonic or time.monotonic()) - run.started_monotonic) * 1000)
    return {
        "query_id": run.query_id,
        "status": run.status,
        "executive_summary": summary,
        "detailed_answer": detailed,
        "key_findings": _key_findings(report.sections),
        "conflicting_viewpoints": _conflicts(report),
        "limitations": _limitations(report),
        "next_questions": report.next_questions,
        "confidence": {
            "overall_score": confidence,
            "label": _confidence_label(confidence),
            "breakdown": _confidence_breakdown(report),
            "uncertainty_notes": _uncertainty_notes(report),
        },
        "sources": [
            {
                "url": s.url,
                "title": s.title,
                "domain": s.domain,
                "trust_score": s.score,
                "snippet": s.snippet,
            }
            for s in report.sources
        ],
        "execution_metadata": {
            "total_latency_ms": latency_ms,
            "pipelines_run": len(run.stages),
            "pipelines_failed": sum(1 for s in run.stages.values() if s.get("status") == "failed"),
            "total_input_tokens": total_in,
            "total_output_tokens": total_out,
            "estimated_cost_usd": total_cost,
            "ensemble_mode": report.ensemble.ensemble_mode if report.ensemble else "single",
            "provider_used": report.provider_used,
        },
        "created_at": report.generated_at,
    }


def _section_body(sections: list[Section], prefix: str) -> str:
    found = next((s for s in sections if s.heading.lower().startswith(prefix)), None)
    return found.body if found else ""


def _key_findings(sections: list[Section]) -> list[str]:
    for section in sections:
        if "finding" in section.heading.lower():
            return _bullets(section.body)
    return _bullets(sections[0].body if sections else "")[:5]


def _bullets(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "*")):
            out.append(stripped.lstrip("-* ").strip())
    return out[:8]


def _conflicts(report: ResearchReport) -> list[str]:
    if report.ensemble and report.ensemble.disagreement_summary:
        return [report.ensemble.disagreement_summary]
    return []


def _limitations(report: ResearchReport) -> list[str]:
    notes = list(report.verifier.notes if report.verifier else [])
    if report.verifier and report.verifier.violations:
        notes.append(f"{len(report.verifier.violations)} citation issue(s) were detected.")
    return notes[:8]


def _confidence_breakdown(report: ResearchReport) -> dict[str, float]:
    if report.ensemble:
        return {
            "provider_agreement": report.ensemble.provider_agreement_score,
            "source_quality": report.ensemble.source_quality_score,
            "factual_consistency": report.ensemble.factual_consistency_score,
            "hallucination_safety": max(0.0, 1.0 - report.ensemble.hallucination_risk),
        }
    overall = report.verifier.overall_confidence if report.verifier else 0.0
    source_quality = min(1.0, sum(s.score for s in report.sources) / max(len(report.sources), 1))
    citation_ok = 0.0 if (report.verifier and report.verifier.violations) else 1.0
    return {
        "provider_agreement": overall,
        "source_quality": source_quality,
        "factual_consistency": overall,
        "hallucination_safety": citation_ok,
    }


def _uncertainty_notes(report: ResearchReport) -> list[str]:
    if report.ensemble and report.ensemble.uncertainty_notes:
        return report.ensemble.uncertainty_notes
    return report.verifier.notes if report.verifier else []


def _confidence_label(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _provider_chain() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in [settings.default_provider, *settings.fallback_chain]:
        lower = name.lower()
        if lower not in seen:
            seen.add(lower)
            out.append(lower)
    return out


def _available_providers() -> list[str]:
    try:
        return [p.name for p in LLMRouter().providers]
    except Exception as exc:
        logger.error("Failed to load providers: %s", exc, exc_info=True)
        return []


def _warnings() -> list[str]:
    if _available_providers():
        return []
    return ["No LLM providers are configured. Set an API key or run local Ollama."]


def _mode_from_frontend(value: str) -> str:
    mapping = {"research": "topic", "technology": "tech"}
    return mapping.get(value, value)


def _effort_from_pipeline_mode(value: str) -> str:
    return {"fast": "low", "balanced": "medium", "deep": "high"}[value]


def _estimate_seconds(effort: str) -> int:
    return {"low": 45, "medium": 90, "high": 180}.get(effort, 90)


def _configure_log_level(verbosity: str) -> None:
    """Map a verbosity label to a Python log level and apply it."""
    mapping = {"quiet": "WARNING", "normal": "INFO", "verbose": "DEBUG", "debug": "DEBUG"}
    level_name = mapping.get(verbosity, "INFO")
    logging.getLogger("researchhq").setLevel(level_name)
    logger.info("Root researchhq logger set to %s", level_name)
