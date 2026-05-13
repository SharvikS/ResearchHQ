"""Multi-dimensional confidence scorer for ensemble research runs.

Score = weighted sum of:
  - provider_agreement (40 %) — how many providers succeeded and agreed
  - source_quality     (25 %) — average ranked-source tier quality
  - factual_consistency(20 %) — fraction of claims without contradiction
  - hallucination_safety(15%) — inverse of hallucination-risk estimate

All sub-scores are 0.0–1.0. The final overall_score is clamped to [0, 1].
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from researchhq.ensemble.consensus import ConsensusResult
from researchhq.ensemble.orchestrator import EnsembleRun

logger = logging.getLogger(__name__)

_WEIGHTS = {
    "provider_agreement":   0.40,
    "source_quality":       0.25,
    "factual_consistency":  0.20,
    "hallucination_safety": 0.15,
}

# Source tier → normalized quality 0.0–1.0
_TIER_QUALITY: dict[str, float] = {
    "official":      1.00,
    "academic":      1.00,
    "government":    0.95,
    "news":          0.80,
    "docs":          0.75,
    "github":        0.70,
    "comparison":    0.60,
    "wiki":          0.55,
    "community":     0.50,
    "social":        0.30,
    "blog":          0.35,
    "low_quality":   0.10,
    "search_engine": 0.20,
    "other":         0.30,
}


@dataclass
class ConfidenceReport:
    overall_score: float                    # 0.0–1.0, final weighted score
    provider_agreement_score: float
    source_quality_score: float
    factual_consistency_score: float
    hallucination_risk: float              # 0=low, 1=high
    breakdown: dict[str, float] = field(default_factory=dict)
    high_confidence_areas: list[str] = field(default_factory=list)
    low_confidence_areas: list[str] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)
    provider_scores: dict[str, float] = field(default_factory=dict)

    @property
    def confidence_label(self) -> str:
        if self.overall_score >= 0.75:
            return "high"
        if self.overall_score >= 0.50:
            return "medium"
        return "low"


def _tier_score(source: Any) -> float:
    tier_val = getattr(source, "tier", None)
    if tier_val is None:
        return 0.30
    tier_str = tier_val.value if hasattr(tier_val, "value") else str(tier_val)
    return _TIER_QUALITY.get(tier_str.lower(), 0.30)


def score_confidence(
    ensemble_run: EnsembleRun,
    consensus: ConsensusResult,
    sources: list,  # list[RankedSource]
) -> ConfidenceReport:
    """Compute multi-dimensional confidence from ensemble results and consensus."""

    # ── Provider agreement (40 %) ────────────────────────────────────────────
    if not ensemble_run.results:
        provider_agreement = 0.0
    else:
        success_rate = len(ensemble_run.successful) / len(ensemble_run.results)
        provider_agreement = success_rate * 0.4 + consensus.overall_agreement_rate * 0.6

    # ── Source quality (25 %) ────────────────────────────────────────────────
    if sources:
        source_quality = sum(_tier_score(s) for s in sources) / len(sources)
    else:
        source_quality = 0.30

    # ── Factual consistency (20 %) ───────────────────────────────────────────
    total_groups = len(consensus.all_groups)
    if total_groups == 0:
        factual_consistency = 0.50
    else:
        contested_ratio = len(consensus.contested_groups) / total_groups
        factual_consistency = max(0.0, 1.0 - contested_ratio * 2.0)

    # ── Hallucination risk (15 %) ────────────────────────────────────────────
    total_claims = consensus.total_claims
    if total_claims == 0:
        hallucination_risk = 0.50
    else:
        unique_claims = sum(len(g.claims) for g in consensus.unique_groups)
        unique_ratio = unique_claims / total_claims

        source_urls: set[str] = {getattr(s, "url", "") for s in sources}
        unsupported_numeric = sum(
            1 for g in consensus.unique_groups
            for c in g.claims
            if c.has_number and not any(u in source_urls for u in c.source_mentions)
        )
        unsupported_ratio = unsupported_numeric / max(total_claims, 1)
        hallucination_risk = min(unique_ratio * 0.5 + unsupported_ratio * 0.5, 1.0)

    # ── Overall ──────────────────────────────────────────────────────────────
    overall = (
        _WEIGHTS["provider_agreement"]   * provider_agreement
        + _WEIGHTS["source_quality"]       * source_quality
        + _WEIGHTS["factual_consistency"]  * factual_consistency
        + _WEIGHTS["hallucination_safety"] * (1.0 - hallucination_risk)
    )
    overall = round(max(0.0, min(1.0, overall)), 3)

    # ── Per-provider scores ───────────────────────────────────────────────────
    provider_scores: dict[str, float] = {}
    for result in ensemble_run.results:
        provider_scores[result.provider] = 0.65 if result.status == "success" else 0.0
    for group in consensus.consensus_groups:
        for p in group.providers_supporting:
            if p in provider_scores:
                provider_scores[p] = min(1.0, provider_scores[p] + 0.05)

    # ── Explanatory areas ────────────────────────────────────────────────────
    high_areas = [g.representative[:80] for g in consensus.consensus_groups[:5]]
    low_areas = [g.representative[:80] for g in consensus.unique_groups[:3]]

    # ── Uncertainty notes ────────────────────────────────────────────────────
    notes: list[str] = []
    if ensemble_run.failed:
        notes.append(
            f"{len(ensemble_run.failed)} provider(s) failed: "
            + ", ".join(r.provider for r in ensemble_run.failed)
        )
    if consensus.contested_groups:
        notes.append(f"{len(consensus.contested_groups)} contested claim group(s) detected")
    if hallucination_risk > 0.40:
        notes.append(
            f"Elevated hallucination risk ({hallucination_risk:.0%}) — "
            "verify statistics independently"
        )
    if not sources:
        notes.append("No sources available for citation verification")

    return ConfidenceReport(
        overall_score=overall,
        provider_agreement_score=round(provider_agreement, 3),
        source_quality_score=round(source_quality, 3),
        factual_consistency_score=round(factual_consistency, 3),
        hallucination_risk=round(hallucination_risk, 3),
        breakdown={
            "provider_agreement":   round(provider_agreement   * _WEIGHTS["provider_agreement"],   3),
            "source_quality":       round(source_quality       * _WEIGHTS["source_quality"],       3),
            "factual_consistency":  round(factual_consistency  * _WEIGHTS["factual_consistency"],  3),
            "hallucination_safety": round((1.0 - hallucination_risk) * _WEIGHTS["hallucination_safety"], 3),
        },
        high_confidence_areas=high_areas,
        low_confidence_areas=low_areas,
        uncertainty_notes=notes,
        provider_scores=provider_scores,
    )
