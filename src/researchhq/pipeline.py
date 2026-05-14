"""High-level orchestration: planner -> searcher -> ranker -> fetcher -> extractor
-> synthesizer (or ensemble) -> verifier -> formatter.

Emits typed PipelineEvents so the CLI and GUI can render whatever they care about.
When settings.ensemble_enabled is True, the synthesizer stage is replaced by the
parallel multi-model ensemble pipeline (see researchhq.ensemble).
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
from researchhq.config import settings
from researchhq.effort import DEFAULT_EFFORT, get_profile, synth_directive
from researchhq.events import PipelineEvent, StageEvent  # noqa: F401 (re-export)
from researchhq.llm.cost_tracker import tracker
from researchhq.llm.router import router as llm_router
from researchhq.modes import get_mode
from researchhq.modes.base import ResearchMode
from researchhq.reports.schema import (
    EnsembleProviderSummary,
    EnsembleReportSection,
    FetchedPageSummary,
    ResearchReport,
    StageCost,
)

logger = logging.getLogger(__name__)


async def _run_ensemble_synthesis(
    mode: ResearchMode,
    query: str,
    ranked: list,
    facts: list,
    pages: list,
    profile,
    emit: Callable,
) -> tuple[list, str, list, "EnsembleReportSection | None"]:
    """Run parallel multi-model synthesis. Returns (sections, provider, violations, meta).

    Falls back to single-provider synthesis if no ensemble providers are available.
    Returns meta=None on fallback so the caller can detect which path was taken.
    """
    from researchhq.ensemble.claim_extractor import extract_all_claims
    from researchhq.ensemble.confidence import score_confidence
    from researchhq.ensemble.consensus import analyze_consensus
    from researchhq.ensemble.disagreement import analyze_disagreements
    from researchhq.ensemble.merger import EnsembleMeta, merge_synthesis
    from researchhq.ensemble.orchestrator import (
        ENSEMBLE_PROFILES,
        EnsembleRun,
        build_ensemble_providers,
        run_parallel,
    )
    from researchhq.ensemble.verifier import verify_synthesis as ensemble_verify

    # Resolve which providers to use
    provider_names = (
        settings.ensemble_providers
        or ENSEMBLE_PROFILES.get(settings.ensemble_mode, ["groq", "gemini"])
    )
    providers = build_ensemble_providers(
        provider_names,
        max_providers=settings.ensemble_max_parallel_providers,
    )

    if not providers:
        logger.warning("Ensemble enabled but no providers available; falling back to single-provider.")
        sections, prov, violations = await synthesizer.synthesize(
            mode, query, ranked, facts, pages,
            max_tokens=profile.synth_max_tokens,
            depth_directive=synth_directive(profile),
            page_budget_chars=profile.synth_page_budget_chars,
        )
        return sections, prov, violations, None

    provider_names_label = " + ".join(p.name for p in providers)
    emit(
        "agent_started", stage="ensemble",
        detail=f"[ensemble: {provider_names_label}] running in parallel",
        providers=[p.name for p in providers],
        ensemble_mode=settings.ensemble_mode,
    )

    # Build the synthesis prompt (same content as synthesizer.synthesize)
    from researchhq.agents.synthesizer import (
        _format_facts,
        _format_pages,
        _format_sources,
        _system,
    )
    depth_dir = synth_directive(profile)
    sys_prompt = _system(mode, depth_dir)
    user_prompt = (
        f"User research query: {query}\n\n"
        f"Extracted facts:\n{_format_facts(facts)}\n\n"
        f"Ranked sources (these URLs are the ONLY allowed citation targets):\n"
        f"{_format_sources(ranked)}\n\n"
        f"Fetched page content (authoritative):\n"
        f"{_format_pages(pages or [], profile.synth_page_budget_chars)}"
    )

    # ── 1. Parallel provider execution ────────────────────────────────────────
    def _on_provider_done(result) -> None:
        icon = "✓" if result.status == "success" else "✗"
        emit(
            "ensemble_provider_finished", stage="ensemble",
            detail=f"{icon} {result.provider} ({result.elapsed:.1f}s, {result.status})",
            provider=result.provider,
            status=result.status,
            elapsed=result.elapsed,
            tokens_in=result.input_tokens,
            tokens_out=result.output_tokens,
            error=result.error or "",
        )

    ensemble_run: EnsembleRun = await run_parallel(
        prompt=user_prompt,
        system=sys_prompt,
        providers=providers,
        query=query,
        timeout=settings.ensemble_provider_timeout,
        max_tokens=profile.synth_max_tokens,
        on_provider_event=_on_provider_done,
    )

    n_ok = len(ensemble_run.successful)
    n_fail = len(ensemble_run.failed)
    emit(
        "ensemble_providers_done", stage="ensemble",
        detail=f"{n_ok}/{len(providers)} succeeded in {ensemble_run.elapsed_total:.1f}s",
        successful=n_ok, failed=n_fail,
        elapsed=ensemble_run.elapsed_total,
    )

    if not ensemble_run.successful:
        from researchhq.reports.schema import Section
        stub = Section(
            heading="Findings",
            body="_Ensemble synthesis failed — all configured providers returned errors._",
        )
        meta = EnsembleReportSection(
            enabled=True,
            ensemble_mode=settings.ensemble_mode,
            providers_attempted=[p.name for p in providers],
            providers_failed=[r.provider for r in ensemble_run.failed],
        )
        return [stub], "ensemble(0)", [], meta

    # ── 2. Claim extraction ───────────────────────────────────────────────────
    emit("agent_progress", stage="ensemble", detail="extracting claims from provider outputs")
    use_llm = (
        settings.ensemble_use_llm_extraction
        and settings.ensemble_mode == "max_confidence"
    )
    claims_by_provider = await extract_all_claims(
        ensemble_run.successful, llm_router, use_llm=use_llm
    )
    total_claims = sum(len(v) for v in claims_by_provider.values())
    emit(
        "ensemble_claims_extracted", stage="ensemble",
        detail=f"{total_claims} claims from {len(claims_by_provider)} providers",
        total_claims=total_claims,
        providers=list(claims_by_provider.keys()),
    )

    # ── 3. Consensus analysis ─────────────────────────────────────────────────
    emit("agent_progress", stage="ensemble", detail="building consensus")
    consensus_result = analyze_consensus(
        claims_by_provider,
        similarity_threshold=settings.ensemble_consensus_threshold,
        min_providers_for_consensus=settings.ensemble_min_providers_consensus,
    )
    emit(
        "ensemble_consensus_ready", stage="ensemble",
        detail=(
            f"{len(consensus_result.consensus_groups)} consensus · "
            f"{len(consensus_result.contested_groups)} contested · "
            f"{len(consensus_result.unique_groups)} unique"
        ),
        consensus=len(consensus_result.consensus_groups),
        contested=len(consensus_result.contested_groups),
        unique=len(consensus_result.unique_groups),
        agreement_rate=consensus_result.overall_agreement_rate,
    )

    # ── 4. Confidence scoring ─────────────────────────────────────────────────
    confidence = score_confidence(ensemble_run, consensus_result, ranked)
    emit(
        "ensemble_confidence_scored", stage="ensemble",
        detail=f"confidence={confidence.overall_score:.0%} ({confidence.confidence_label})",
        confidence=confidence.overall_score,
        label=confidence.confidence_label,
        provider_agreement=confidence.provider_agreement_score,
        hallucination_risk=confidence.hallucination_risk,
    )

    # ── 5. Disagreement analysis ──────────────────────────────────────────────
    disagreements = analyze_disagreements(consensus_result)
    if disagreements.has_major_conflicts:
        emit(
            "ensemble_disagreements_found", stage="ensemble",
            detail=f"⚠ {disagreements.major_count} major + {disagreements.minor_count} minor conflicts",
            major=disagreements.major_count,
            moderate=disagreements.moderate_count,
            minor=disagreements.minor_count,
            summary=disagreements.summary,
        )

    # ── 6. Meta-synthesis merge ───────────────────────────────────────────────
    emit("agent_progress", stage="ensemble", detail="merging into final synthesis")
    sections, provider_label, violations = await merge_synthesis(
        mode, query, ensemble_run, consensus_result,
        confidence, disagreements, ranked,
        ensemble_mode=settings.ensemble_mode,
        max_tokens=max(profile.synth_max_tokens, 3000),
    )
    emit(
        "ensemble_merge_done", stage="ensemble",
        detail=f"{len(sections)} sections produced",
        sections=len(sections),
        provider_label=provider_label,
    )

    # ── 7. Post-synthesis verification ───────────────────────────────────────
    verifier_note = ensemble_verify(sections, ensemble_run, confidence, ranked)

    emit(
        "agent_finished", stage="ensemble",
        detail=(
            f"{len(sections)} sections · conf={verifier_note.adjusted_confidence:.0%} "
            f"({verifier_note.support_strength} support) · {provider_label}"
        ),
        confidence=verifier_note.adjusted_confidence,
        support_strength=verifier_note.support_strength,
        provider_label=provider_label,
        consensus_groups=len(consensus_result.consensus_groups),
        contested_groups=len(consensus_result.contested_groups),
    )

    # ── 8. Build serialisable report section ─────────────────────────────────
    provider_summaries = [
        EnsembleProviderSummary(
            provider=r.provider,
            model=r.model,
            status=r.status,
            elapsed=round(r.elapsed, 2),
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            error=r.error,
        )
        for r in ensemble_run.results
    ]
    meta = EnsembleReportSection(
        enabled=True,
        ensemble_mode=settings.ensemble_mode,
        providers_attempted=[p.name for p in providers],
        providers_succeeded=[r.provider for r in ensemble_run.successful],
        providers_failed=[r.provider for r in ensemble_run.failed],
        provider_summaries=provider_summaries,
        consensus_groups=len(consensus_result.consensus_groups),
        contested_groups=len(consensus_result.contested_groups),
        unique_groups=len(consensus_result.unique_groups),
        overall_agreement_rate=consensus_result.overall_agreement_rate,
        overall_confidence=confidence.overall_score,
        adjusted_confidence=verifier_note.adjusted_confidence,
        provider_agreement_score=confidence.provider_agreement_score,
        source_quality_score=confidence.source_quality_score,
        factual_consistency_score=confidence.factual_consistency_score,
        hallucination_risk=confidence.hallucination_risk,
        confidence_label=confidence.confidence_label,
        support_strength=verifier_note.support_strength,
        total_disagreements=len(disagreements.disagreements),
        major_disagreements=disagreements.major_count,
        disagreement_summary=disagreements.summary,
        total_elapsed=round(ensemble_run.elapsed_total, 2),
        uncertainty_notes=confidence.uncertainty_notes,
        provider_scores=confidence.provider_scores,
    )

    return sections, provider_label, violations, meta


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

    # ----- Query Understanding -----
    from researchhq.agents.query_understanding import classify as classify_query
    emit("agent_started", stage="query_understanding", detail="classifying intent and complexity")
    query_intent = await classify_query(query)
    emit(
        "agent_finished", stage="query_understanding",
        detail=(
            f"intent={query_intent.intent_type} domain={query_intent.domain} "
            f"complexity={query_intent.complexity} mode={query_intent.recommended_pipeline_mode}"
        ),
        intent_type=query_intent.intent_type,
        domain=query_intent.domain,
        complexity=query_intent.complexity,
        recommended_mode=query_intent.recommended_pipeline_mode,
        requires_web=query_intent.requires_web_search,
        requires_code=query_intent.requires_code_analysis,
    )
    _check_cancel()

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

    # ----- Synthesizer (single-provider) or Ensemble -----
    ensemble_meta = None
    if settings.ensemble_enabled:
        sections, provider, synth_violations, ensemble_meta = await _run_ensemble_synthesis(
            mode, query, ranked, facts, pages, profile, emit
        )
        emit_llm_delta("ensemble")
    else:
        emit("agent_started", stage="synthesizer", detail="composing sections")
        sections, provider, synth_violations = await synthesizer.synthesize(
            mode, query, ranked, facts, pages,
            max_tokens=profile.synth_max_tokens,
            depth_directive=synth_directive(profile),
            page_budget_chars=profile.synth_page_budget_chars,
        )
        emit_llm_delta("synthesizer")
    for s in sections:
        emit("report_section_ready", stage="synthesizer" if not settings.ensemble_enabled else "ensemble",
             heading=s.heading, body_preview=s.body[:200])
    if not settings.ensemble_enabled:
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
        ensemble=ensemble_meta,
    )

    ensemble_conf = (
        ensemble_meta.adjusted_confidence if ensemble_meta else note.overall_confidence
    )
    summary_data = {
        "elapsed_s": elapsed,
        "sources": len(ranked),
        "facts": len(facts),
        "sections": len(sections),
        "confidence": ensemble_conf,
        "provider_used": provider,
        "ensemble_enabled": settings.ensemble_enabled,
        "ensemble_mode": settings.ensemble_mode if settings.ensemble_enabled else "",
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
