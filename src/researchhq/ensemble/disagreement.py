"""Disagreement analyzer — identifies and characterizes conflicting claims.

Works on contested ClaimGroups from the consensus engine. Outputs a
structured DisagreementReport that the merger includes in the final synthesis
as explicit uncertainty markers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from researchhq.ensemble.consensus import ClaimGroup, ConsensusResult

logger = logging.getLogger(__name__)


@dataclass
class Disagreement:
    topic: str
    claim_a: str
    provider_a: str
    claim_b: str
    provider_b: str
    severity: str = "minor"          # minor | moderate | major
    resolution: Optional[str] = None
    contradiction_note: Optional[str] = None


@dataclass
class DisagreementReport:
    disagreements: list[Disagreement] = field(default_factory=list)
    agreement_rate: float = 1.0
    total_contested: int = 0
    major_count: int = 0
    moderate_count: int = 0
    minor_count: int = 0
    summary: str = ""

    @property
    def has_major_conflicts(self) -> bool:
        return self.major_count > 0


def _severity(group: ClaimGroup) -> str:
    note = group.contradiction_note or ""
    if "numeric disagreement" in note:
        return "major"
    if "conflicting sentiment" in note:
        return "moderate"
    return "minor"


def _resolution(d: Disagreement) -> str:
    if d.severity == "major":
        return "Verify with primary sources — significant numeric discrepancy detected"
    if d.severity == "moderate":
        return "Both perspectives may be valid in different contexts or time frames"
    return "Minor phrasing difference — providers likely refer to the same concept"


def analyze_disagreements(consensus: ConsensusResult) -> DisagreementReport:
    """Produce a DisagreementReport from all contested ClaimGroups."""
    disagreements: list[Disagreement] = []

    for group in consensus.contested_groups:
        if len(group.claims) < 2:
            continue
        severity = _severity(group)
        topic = group.representative[:100]
        seen: set[tuple[str, str]] = set()

        for i in range(len(group.claims)):
            for j in range(i + 1, len(group.claims)):
                ca, cb = group.claims[i], group.claims[j]
                if ca.provider == cb.provider:
                    continue
                pair = tuple(sorted([ca.provider, cb.provider]))
                if pair in seen:
                    continue
                seen.add(pair)  # type: ignore[arg-type]

                d = Disagreement(
                    topic=topic,
                    claim_a=ca.text[:220] + ("…" if len(ca.text) > 220 else ""),
                    provider_a=ca.provider,
                    claim_b=cb.text[:220] + ("…" if len(cb.text) > 220 else ""),
                    provider_b=cb.provider,
                    severity=severity,
                    contradiction_note=group.contradiction_note,
                )
                d.resolution = _resolution(d)
                disagreements.append(d)

    major = sum(1 for d in disagreements if d.severity == "major")
    moderate = sum(1 for d in disagreements if d.severity == "moderate")
    minor = sum(1 for d in disagreements if d.severity == "minor")

    total_groups = len(consensus.all_groups)
    contested = len(consensus.contested_groups)
    agreement_rate = 1.0 - (contested / max(total_groups, 1))

    if not disagreements:
        summary = "No significant disagreements detected across providers."
    elif major > 0:
        summary = (
            f"{len(disagreements)} disagreements: {major} major (numeric conflicts), "
            f"{moderate} moderate, {minor} minor. Verify key statistics independently."
        )
    else:
        summary = (
            f"{len(disagreements)} minor disagreement(s) detected. "
            "Providers broadly agree on core findings."
        )

    return DisagreementReport(
        disagreements=disagreements,
        agreement_rate=round(agreement_rate, 3),
        total_contested=contested,
        major_count=major,
        moderate_count=moderate,
        minor_count=minor,
        summary=summary,
    )
