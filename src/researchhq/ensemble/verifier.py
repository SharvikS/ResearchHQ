"""Ensemble verifier — post-synthesis quality gate.

Validates the final synthesis against source evidence, checks citation
coverage, and adjusts the confidence score downward for failures.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from researchhq.ensemble.confidence import ConfidenceReport
from researchhq.ensemble.orchestrator import EnsembleRun
from researchhq.reports.schema import Section

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s\)\]]+")


@dataclass
class EnsembleVerifierNote:
    adjusted_confidence: float
    original_confidence: float
    adjustments: list[str] = field(default_factory=list)
    verification_notes: list[str] = field(default_factory=list)
    provider_matrix_summary: str = ""
    support_strength: str = "medium"   # weak | medium | strong


def _cited_urls(sections: list[Section]) -> set[str]:
    urls: set[str] = set()
    for sec in sections:
        urls.update(_URL_RE.findall(sec.body))
    return urls


def _source_coverage(cited: set[str], sources: list) -> float:
    if not cited:
        return 1.0
    known = {getattr(s, "url", "") for s in sources}
    valid = sum(1 for u in cited if u in known)
    return valid / len(cited)


def verify_synthesis(
    sections: list[Section],
    ensemble_run: EnsembleRun,
    confidence: ConfidenceReport,
    sources: list,  # list[RankedSource]
) -> EnsembleVerifierNote:
    """Validate the final synthesis and return an adjusted confidence note."""
    adjusted = confidence.overall_score
    adjustments: list[str] = []
    notes: list[str] = []

    # Check 1: citation validity
    cited = _cited_urls(sections)
    coverage = _source_coverage(cited, sources)
    if coverage < 0.70:
        penalty = 0.05
        adjusted -= penalty
        adjustments.append(f"source coverage {coverage:.0%} < 70 % — −{penalty:.0%}")

    # Check 2: provider success rate
    if ensemble_run.success_rate < 0.50:
        penalty = 0.10
        adjusted -= penalty
        adjustments.append(
            f"only {ensemble_run.success_rate:.0%} providers succeeded — −{penalty:.0%}"
        )

    # Check 3: hallucination risk
    if confidence.hallucination_risk > 0.50:
        penalty = 0.08
        adjusted -= penalty
        adjustments.append(
            f"hallucination risk {confidence.hallucination_risk:.0%} > 50 % — −{penalty:.0%}"
        )

    # Informational notes
    if ensemble_run.successful:
        notes.append(
            "Synthesis covers "
            + ", ".join(r.provider for r in ensemble_run.successful)
        )
    if ensemble_run.failed:
        notes.append(
            "Degraded ensemble — failed: "
            + ", ".join(r.provider for r in ensemble_run.failed)
        )
    notes.extend(confidence.uncertainty_notes)

    # Support strength
    n_ok = len(ensemble_run.successful)
    pa = confidence.provider_agreement_score
    if n_ok >= 3 and pa >= 0.60:
        support = "strong"
    elif n_ok >= 2 or pa >= 0.40:
        support = "medium"
    else:
        support = "weak"

    # Provider matrix summary
    ps = confidence.provider_scores
    matrix_str = " | ".join(f"{p}: {s:.0%}" for p, s in sorted(ps.items())) if ps else "n/a"

    return EnsembleVerifierNote(
        adjusted_confidence=round(max(0.0, min(1.0, adjusted)), 3),
        original_confidence=confidence.overall_score,
        adjustments=adjustments,
        verification_notes=notes,
        provider_matrix_summary=matrix_str,
        support_strength=support,
    )
