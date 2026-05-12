"""High-level orchestration: planner -> searcher -> ranker -> fetcher -> extractor
-> synthesizer -> verifier -> formatter.

Emits typed PipelineEvents so the CLI and GUI can render whatever they care about.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable

from researchhq.agents import (
    extractor,
    fetcher,
    formatter,
    planner,
    searcher,
    source_ranker,
    synthesizer,
    verifier,
)
from researchhq.effort import DEFAULT_EFFORT, get_profile, synth_directive
from researchhq.events import PipelineEvent, StageEvent  # noqa: F401 (re-export)
from researchhq.llm.cost_tracker import tracker
from researchhq.modes import get_mode
from researchhq.modes.base import ResearchMode
from researchhq.reports.schema import (
    FetchedPageSummary,
    ResearchReport,
    StageCost,
)

logger = logging.getLogger(__name__)


async def run(
    mode_name: str,
    query: str,
    on_event: "Callable[[PipelineEvent], None] | None" = None,
    cancel_check: "Callable[[], bool] | None" = None,
    effort: str = DEFAULT_EFFORT,
) -> ResearchReport:
    """Execute the full research pipeline. Reset cost tracker per run.

    on_event(PipelineEvent) is called for every transition. Cancellation: pass
    `cancel_check`; the next stage boundary raises asyncio.CancelledError.

    `effort` (low|medium|high) dials depth across every stage — number of search
    queries, sources kept, pages fetched, token budgets, and synthesizer
    verbosity. See researchhq.effort for the profile values.
    """
    mode: ResearchMode = get_mode(mode_name)
    profile = get_profile(effort)
    tracker.reset_for_run()

    # snapshot tracker call count before/after each LLM stage to derive llm_call_finished events.
    prev_calls = 0
    started_at = time.monotonic()

    def emit(type_: str, stage: str = "", detail: str = "", **data: object) -> None:
        if on_event is None:
            return
        try:
            on_event(PipelineEvent(type=type_, stage=stage, detail=detail, data=dict(data)))
        except Exception:  # noqa: BLE001 - never let UI errors break the pipeline
            logger.exception("on_event handler raised; continuing pipeline")

    def emit_llm_delta(stage: str) -> None:
        """After an LLM-using stage, emit one llm_call_finished per new tracker record."""
        nonlocal prev_calls
        records = tracker.records
        new = records[prev_calls:]
        for r in new:
            emit(
                "llm_call_finished",
                stage=stage,
                detail=f"{r.provider}/{r.model}",
                provider=r.provider, model=r.model,
                input_tokens=r.input_tokens, output_tokens=r.output_tokens,
                equivalent_cost_usd=r.equivalent_cost_usd, stage_tag=r.stage,
            )
        prev_calls = len(records)

    def _check_cancel() -> None:
        if cancel_check and cancel_check():
            raise asyncio.CancelledError("pipeline canceled")

    emit("run_started", detail=query, mode=mode.name, query=query, effort=profile.name)

    # ----- Planner -----
    emit("agent_started", stage="planner", detail=f"decomposing query (effort={profile.name})")
    plan = await planner.plan(
        mode, query,
        min_queries=profile.planner_min_queries,
        max_queries=profile.planner_max_queries,
        max_tokens=profile.planner_max_tokens,
    )
    emit_llm_delta("planner")
    emit("agent_finished", stage="planner",
         detail=f"{len(plan.queries)} queries planned",
         queries=list(plan.queries))
    _check_cancel()

    # ----- Searcher -----
    emit("agent_started", stage="searcher", detail="running searches")
    raw = await searcher.search_all(plan.queries, results_per_query=profile.results_per_query)
    for r in raw:
        emit("source_found", stage="searcher",
             url=r.url, title=r.title, snippet=r.snippet[:280])
    emit("agent_finished", stage="searcher", detail=f"{len(raw)} unique results",
         count=len(raw))
    _check_cancel()

    # ----- Ranker -----
    emit("agent_started", stage="source_ranker", detail="classifying & ranking")
    ranked = source_ranker.rank(raw, mode, subject=query, cap=profile.max_total_sources)
    top_tier = ranked[0].tier.value if ranked else "n/a"
    emit("agent_finished", stage="source_ranker",
         detail=f"{len(ranked)} kept; top tier: {top_tier}",
         count=len(ranked), top_tier=top_tier)
    _check_cancel()

    # ----- Fetcher -----
    emit("agent_started", stage="fetcher", detail="fetching top-N pages")
    pages = await fetcher.fetch_top(
        ranked,
        max_fetch=profile.fetch_top_n,
        per_page_chars=profile.per_page_chars,
    )
    fetched_ok = sum(1 for p in pages if p.text)
    emit("agent_finished", stage="fetcher",
         detail=f"{fetched_ok}/{len(pages)} pages",
         fetched=fetched_ok, attempted=len(pages))
    _check_cancel()

    # ----- Extractor -----
    emit("agent_started", stage="extractor", detail="extracting facts")
    facts, extractor_violations = await extractor.extract(
        query, ranked, pages,
        max_tokens=profile.extractor_max_tokens,
        min_facts=profile.extractor_min_facts,
    )
    emit_llm_delta("extractor")
    emit("agent_finished", stage="extractor",
         detail=f"{len(facts)} facts; {len(extractor_violations)} violation(s)",
         facts=len(facts), violations=len(extractor_violations))
    _check_cancel()

    # ----- Synthesizer -----
    emit("agent_started", stage="synthesizer", detail="composing sections")
    sections, provider, synth_violations = await synthesizer.synthesize(
        mode, query, ranked, facts, pages,
        max_tokens=profile.synth_max_tokens,
        depth_directive=synth_directive(profile),
        page_budget_chars=profile.synth_page_budget_chars,
    )
    emit_llm_delta("synthesizer")
    for s in sections:
        emit("report_section_ready", stage="synthesizer",
             heading=s.heading, body_preview=s.body[:200])
    emit("agent_finished", stage="synthesizer",
         detail=f"{len(sections)} sections via {provider}",
         provider=provider, sections=len(sections),
         violations=len(synth_violations))
    _check_cancel()

    # ----- Verifier -----
    emit("agent_started", stage="verifier", detail="rule checks + confidence")
    note = verifier.verify(
        mode, ranked, facts,
        sections=sections,
        violations=extractor_violations + synth_violations,
    )
    fails = sum(1 for r in note.rules if not r.passed)
    emit("agent_finished", stage="verifier",
         detail=f"confidence {note.overall_confidence:.2f}; {fails} rule(s) failed",
         confidence=note.overall_confidence, rules_failed=fails,
         rules_total=len(note.rules))
    _check_cancel()

    # ----- Formatter -----
    emit("agent_started", stage="formatter", detail="next research questions")
    next_qs = await formatter.next_questions(
        mode, query, sections,
        min_q=profile.formatter_min_q,
        max_q=profile.formatter_max_q,
    )
    emit_llm_delta("formatter")
    emit("agent_finished", stage="formatter", detail=f"{len(next_qs)} follow-ups",
         count=len(next_qs))

    stage_costs = [
        StageCost(stage=stage, **stats)
        for stage, stats in tracker.by_stage().items()
    ]
    elapsed = round(time.monotonic() - started_at, 2)

    report = ResearchReport(
        mode=mode.name,
        query=query,
        effort=profile.name,
        plan=plan,
        sources=ranked,
        fetched_pages=[
            FetchedPageSummary(
                url=p.url, title=p.title, status=p.status,
                chars=len(p.text), truncated=p.truncated,
            )
            for p in pages
        ],
        facts=facts,
        sections=sections,
        verifier=note,
        next_questions=next_qs,
        stage_costs=stage_costs,
        provider_used=provider,
    )

    summary_data = {
        "elapsed_s": elapsed,
        "sources": len(ranked),
        "facts": len(facts),
        "sections": len(sections),
        "confidence": note.overall_confidence,
        "provider_used": provider,
        "llm_calls": len(tracker.records),
        "input_tokens": sum(r.input_tokens for r in tracker.records),
        "output_tokens": sum(r.output_tokens for r in tracker.records),
        "equivalent_cost_usd": round(
            sum(r.equivalent_cost_usd for r in tracker.records), 4
        ),
    }
    emit("run_completed", detail=f"completed in {elapsed:.1f}s", **summary_data)
    return report


async def stream_events(mode_name: str, query: str) -> AsyncIterator[PipelineEvent]:  # pragma: no cover
    queue: list[PipelineEvent] = []

    def collector(ev: PipelineEvent) -> None:
        queue.append(ev)

    await run(mode_name, query, on_event=collector)
    for ev in queue:
        yield ev
