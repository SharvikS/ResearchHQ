"""Ensemble merger — generates the final synthesized report.

Takes all provider outputs + consensus + confidence + disagreements and issues
one meta-synthesis LLM call that produces the structured final report. Falls
back to the longest successful provider output if the meta-call fails.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from researchhq.agents.citation_guard import CitationViolation, strip_unknown_citations
from researchhq.ensemble.confidence import ConfidenceReport
from researchhq.ensemble.consensus import ConsensusResult
from researchhq.ensemble.disagreement import DisagreementReport
from researchhq.ensemble.orchestrator import EnsembleRun, ProviderResult
from researchhq.llm.router import router
from researchhq.modes.base import ResearchMode
from researchhq.reports.schema import Section
from researchhq.search.source_quality import RankedSource

logger = logging.getLogger(__name__)

# Max chars per provider output sent to meta-synthesis prompt
_BUDGET_PER_PROVIDER: dict[str, int] = {
    "cheap":          3_000,
    "balanced":       6_000,
    "max_confidence": 12_000,
}

# Max consensus/unique groups to include in the prompt
_MAX_CONSENSUS_IN_PROMPT = 25
_MAX_UNIQUE_IN_PROMPT = 12
_MAX_CONTESTED_IN_PROMPT = 8


@dataclass
class EnsembleMeta:
    """Summary attached to ResearchReport when ensemble mode ran."""
    providers_attempted: list[str] = field(default_factory=list)
    providers_succeeded: list[str] = field(default_factory=list)
    providers_failed: list[str] = field(default_factory=list)
    provider_results: list[ProviderResult] = field(default_factory=list)
    consensus: Optional[ConsensusResult] = None
    confidence: Optional[ConfidenceReport] = None
    disagreements: Optional[DisagreementReport] = None
    ensemble_mode: str = "balanced"
    total_elapsed: float = 0.0
    consensus_groups_count: int = 0
    contested_groups_count: int = 0


# ── Prompt construction ────────────────────────────────────────────────────────

def _format_provider_outputs(results: list[ProviderResult], budget: int) -> str:
    parts: list[str] = []
    for r in results:
        header = f"\n### {r.provider.upper()} (model: {r.model or 'unknown'})\n"
        body = r.text
        if len(body) > budget:
            body = body[:budget] + "\n[...truncated]"
        parts.append(header + body)
    return "\n".join(parts)


def _format_consensus(consensus: ConsensusResult) -> str:
    lines: list[str] = []

    if consensus.consensus_groups:
        lines.append(
            f"\n**CONSENSUS CLAIMS** ({len(consensus.consensus_groups)} groups — "
            "state these confidently):"
        )
        for g in consensus.consensus_groups[:_MAX_CONSENSUS_IN_PROMPT]:
            providers = ", ".join(g.providers_supporting)
            lines.append(f"  [{providers}] {g.representative[:200]}")

    if consensus.contested_groups:
        lines.append(
            f"\n**CONTESTED CLAIMS** ({len(consensus.contested_groups)} conflicts — "
            "present both sides):"
        )
        for g in consensus.contested_groups[:_MAX_CONTESTED_IN_PROMPT]:
            if len(g.claims) >= 2:
                ca, cb = g.claims[0], g.claims[1]
                lines.append(f"  [{ca.provider}]: {ca.text[:140]}")
                lines.append(f"  [{cb.provider}]: {cb.text[:140]}")
                if g.contradiction_note:
                    lines.append(f"  ⚠ {g.contradiction_note}")

    if consensus.unique_groups:
        lines.append(
            f"\n**UNVERIFIED CLAIMS** ({len(consensus.unique_groups)} single-provider — "
            "flag as unconfirmed):"
        )
        for g in consensus.unique_groups[:_MAX_UNIQUE_IN_PROMPT]:
            providers = ", ".join(g.providers_supporting)
            lines.append(f"  [{providers} only] {g.representative[:140]}")

    return "\n".join(lines)


def _format_sources(sources: list[RankedSource]) -> str:
    if not sources:
        return "(no sources)"
    return "\n".join(
        f"  [{i}] ({s.tier.value}) {s.title} — {s.url}"
        for i, s in enumerate(sources, 1)
    )


def _meta_system(mode: ResearchMode) -> str:
    from researchhq.agents.synthesizer import _section_brief
    sections = _section_brief(mode)
    persona = mode.config.synthesizer_persona or "You are a senior research analyst."
    return f"""{persona}

You are synthesizing outputs from MULTIPLE independent AI models into one authoritative research report.

SYNTHESIS RULES:
1. CONSENSUS claims (2+ providers agree) → state confidently, integrate naturally
2. CONTESTED claims (providers disagree) → present both perspectives explicitly
   e.g. "While [Provider A] reports X, [Provider B] indicates Y"
3. UNVERIFIED claims (single provider only) → flag with "according to one source" or "unconfirmed"
4. DEDUPLICATE — merge similar content from multiple providers into one clear statement
5. CITE inline using markdown [text](URL) — ONLY URLs from RANKED SOURCES below
6. Do NOT invent URLs, statistics, dates, or named entities
7. Mark gaps as "insufficient data available"

Report sections (use these exact headings in order):
{sections}

Output ONLY the markdown for the report sections. Do not output source lists or score sections."""


def _meta_user(
    query: str,
    ensemble_run: EnsembleRun,
    consensus: ConsensusResult,
    confidence: ConfidenceReport,
    disagreements: DisagreementReport,
    sources: list[RankedSource],
    budget: int,
) -> str:
    providers_ok = " + ".join(r.provider for r in ensemble_run.successful)
    failed_note = ""
    if ensemble_run.failed:
        failed_note = (
            f" [{len(ensemble_run.failed)} failed: "
            + ", ".join(r.provider for r in ensemble_run.failed) + "]"
        )

    return f"""Research query: {query}

[ENSEMBLE MODE: {providers_ok}{failed_note} | confidence={confidence.overall_score:.0%}]

=== PROVIDER OUTPUTS ===
{_format_provider_outputs(ensemble_run.successful, budget)}

=== CONSENSUS ANALYSIS ===
{_format_consensus(consensus)}

=== DISAGREEMENT SUMMARY ===
{disagreements.summary}
Agreement rate: {disagreements.agreement_rate:.0%}
{f"⚠ {disagreements.major_count} MAJOR conflicts — verify independently" if disagreements.has_major_conflicts else ""}

=== RANKED SOURCES (ONLY cite these URLs) ===
{_format_sources(sources)}"""


# ── Main merge function ────────────────────────────────────────────────────────

async def merge_synthesis(
    mode: ResearchMode,
    query: str,
    ensemble_run: EnsembleRun,
    consensus: ConsensusResult,
    confidence: ConfidenceReport,
    disagreements: DisagreementReport,
    sources: list[RankedSource],
    *,
    ensemble_mode: str = "balanced",
    max_tokens: int = 3500,
    on_event: Optional[Callable] = None,
) -> tuple[list[Section], str, list[CitationViolation]]:
    """Generate the final synthesized report from ensemble analysis.

    Falls back to the longest successful provider output if the meta-synthesis
    LLM call fails, so the pipeline always produces a result.
    """
    if not ensemble_run.successful:
        stub = Section(
            heading="Findings",
            body="_Ensemble synthesis failed — no providers returned successful outputs._",
        )
        return [stub], "ensemble(0)", []

    budget = _BUDGET_PER_PROVIDER.get(ensemble_mode, 6_000)
    system = _meta_system(mode)
    user = _meta_user(
        query, ensemble_run, consensus, confidence, disagreements, sources, budget
    )
    provider_label = f"ensemble({len(ensemble_run.successful)})"

    try:
        response = await router.complete(
            prompt=user, system=system,
            max_tokens=max_tokens,
            stage="ensemble_merge",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Ensemble meta-synthesis failed (%s) — falling back to best provider.", e)
        best = max(ensemble_run.successful, key=lambda r: len(r.text))
        stub = Section(
            heading="Findings",
            body=(
                f"_Meta-synthesis unavailable ({type(e).__name__}). "
                f"Showing output from {best.provider}._\n\n{best.text}"
            ),
        )
        return [stub], provider_label, []

    # Parse sections
    from researchhq.agents.synthesizer import _split_markdown_sections
    raw_sections = _split_markdown_sections(response.text, mode)

    # Strip unknown citations
    known_urls = [s.url for s in sources]
    cleaned: list[Section] = []
    violations: list[CitationViolation] = []
    for sec in raw_sections:
        clean_body, sec_viol = strip_unknown_citations(sec.body, known_urls, location=sec.heading)
        cleaned.append(Section(heading=sec.heading, body=clean_body))
        violations.extend(sec_viol)

    if violations:
        logger.info("Ensemble merger stripped %d unknown citation(s)", len(violations))

    return cleaned, provider_label, violations
