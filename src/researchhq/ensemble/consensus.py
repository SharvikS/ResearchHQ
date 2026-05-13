"""Consensus engine — groups similar claims, detects agreements and contradictions.

Uses Jaccard word-overlap similarity (no external ML deps). Two claims are
"similar" if their non-stopword word sets overlap above a threshold. Groups
are then classified:
  - consensus  : 2+ providers support the same idea
  - contested  : providers give conflicting values / sentiments
  - unique     : only one provider mentions the claim
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from researchhq.ensemble.claim_extractor import Claim

logger = logging.getLogger(__name__)

_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "of", "to", "in", "for", "on",
    "with", "at", "by", "from", "as", "this", "that", "these", "those",
    "it", "its", "and", "or", "but", "not", "also", "than", "then",
    "more", "very", "so", "such", "there", "their", "they", "we", "our",
    "one", "two", "three", "can", "all", "both", "each", "its", "been",
    "which", "what", "when", "where", "how", "why", "who",
})

_NUMERIC_RE = re.compile(r"\b(\d[\d,.]*)(?:\s*[%$BbMmKkTt])?\b")

_POSITIVE_WORDS = frozenset({
    "increase", "growth", "improved", "higher", "better", "rising",
    "leading", "advantage", "gain", "ahead", "stronger", "outperform",
})
_NEGATIVE_WORDS = frozenset({
    "decrease", "decline", "worse", "lower", "falling", "lagging",
    "behind", "disadvantage", "loss", "weaker", "underperform",
})


@dataclass
class ClaimGroup:
    representative: str                         # most representative claim text
    claims: list[Claim] = field(default_factory=list)
    providers_supporting: list[str] = field(default_factory=list)
    agreement_score: float = 0.0               # fraction of total providers
    claim_type: str = "fact"
    is_contested: bool = False
    contradiction_note: Optional[str] = None


@dataclass
class ConsensusResult:
    total_providers: int
    consensus_groups: list[ClaimGroup] = field(default_factory=list)
    contested_groups: list[ClaimGroup] = field(default_factory=list)
    unique_groups: list[ClaimGroup] = field(default_factory=list)
    provider_agreement_matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    overall_agreement_rate: float = 0.0

    @property
    def all_groups(self) -> list[ClaimGroup]:
        return self.consensus_groups + self.contested_groups + self.unique_groups

    @property
    def total_claims(self) -> int:
        return sum(len(g.claims) for g in self.all_groups)


# ── Similarity ─────────────────────────────────────────────────────────────────

def _words(text: str) -> frozenset[str]:
    return frozenset(
        w for w in re.findall(r"\b[a-z]{3,}\b", text.lower())
        if w not in _STOPWORDS
    )


def jaccard_similarity(a: str, b: str) -> float:
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    union = len(wa | wb)
    return inter / union if union > 0 else 0.0


# ── Contradiction detection ────────────────────────────────────────────────────

def _is_contradictory(group: ClaimGroup) -> tuple[bool, Optional[str]]:
    """Detect numeric or sentiment contradictions within a claim group."""
    claims = group.claims
    if len(claims) < 2:
        return False, None

    # Numeric disagreement: same concept, significantly different numbers
    all_nums: list[float] = []
    for c in claims:
        for m in _NUMERIC_RE.finditer(c.text):
            try:
                all_nums.append(float(m.group(1).replace(",", "")))
            except ValueError:
                pass
    if len(all_nums) >= 2:
        mn, mx = min(all_nums), max(all_nums)
        if mn > 0 and mx / mn > 2.5:
            return True, f"numeric disagreement: {mn:g} vs {mx:g}"

    # Sentiment contradiction across providers
    provider_sentiments: dict[str, tuple[bool, bool]] = {}
    for c in claims:
        cw = _words(c.text)
        has_pos = bool(_POSITIVE_WORDS & cw)
        has_neg = bool(_NEGATIVE_WORDS & cw)
        provider_sentiments[c.provider] = (has_pos, has_neg)

    sentiments = list(provider_sentiments.values())
    has_any_pos = any(s[0] for s in sentiments)
    has_any_neg = any(s[1] for s in sentiments)
    if has_any_pos and has_any_neg:
        return True, "conflicting sentiment across providers"

    return False, None


# ── Provider agreement matrix ──────────────────────────────────────────────────

def _build_agreement_matrix(
    claims_by_provider: dict[str, list[Claim]],
) -> dict[str, dict[str, float]]:
    providers = list(claims_by_provider.keys())
    matrix: dict[str, dict[str, float]] = {p: {} for p in providers}

    for i, pa in enumerate(providers):
        for pb in providers[i:]:
            if pa == pb:
                matrix[pa][pb] = 1.0
                continue
            ca_list = claims_by_provider[pa]
            cb_list = claims_by_provider[pb]
            if not ca_list or not cb_list:
                score = 0.0
            else:
                scores = [
                    max(jaccard_similarity(ca.text, cb.text) for cb in cb_list)
                    for ca in ca_list
                ]
                score = sum(scores) / len(scores)
            matrix[pa][pb] = round(score, 3)
            matrix[pb][pa] = round(score, 3)

    return matrix


# ── Main analysis ──────────────────────────────────────────────────────────────

def analyze_consensus(
    claims_by_provider: dict[str, list[Claim]],
    *,
    similarity_threshold: float = 0.35,
    min_providers_for_consensus: int = 2,
) -> ConsensusResult:
    """Group claims, identify consensus, contested, and unique ideas.

    Algorithm:
    1. Flatten all claims into a pool.
    2. Greedy grouping: assign each ungrouped claim to the nearest group
       (Jaccard > threshold), or start a new group.
    3. For each group, classify by provider support count and contradiction.
    """
    total_providers = len(claims_by_provider)
    agreement_matrix = _build_agreement_matrix(claims_by_provider)

    all_claims: list[Claim] = [c for claims in claims_by_provider.values() for c in claims]
    if not all_claims:
        return ConsensusResult(
            total_providers=total_providers,
            provider_agreement_matrix=agreement_matrix,
        )

    # Greedy grouping
    groups: list[list[Claim]] = []
    assigned: set[int] = set()

    for i, anchor in enumerate(all_claims):
        if i in assigned:
            continue
        group = [anchor]
        assigned.add(i)
        for j in range(i + 1, len(all_claims)):
            if j in assigned:
                continue
            if jaccard_similarity(anchor.text, all_claims[j].text) >= similarity_threshold:
                group.append(all_claims[j])
                assigned.add(j)
        groups.append(group)

    consensus_groups: list[ClaimGroup] = []
    contested_groups: list[ClaimGroup] = []
    unique_groups: list[ClaimGroup] = []

    for group_claims in groups:
        providers_in_group = list(dict.fromkeys(c.provider for c in group_claims))
        n_providers = len(providers_in_group)
        agreement = n_providers / max(total_providers, 1)

        # Dominant claim type
        type_counts: dict[str, int] = {}
        for c in group_claims:
            type_counts[c.claim_type] = type_counts.get(c.claim_type, 0) + 1
        claim_type = max(type_counts, key=type_counts.get)  # type: ignore[arg-type]

        # Representative: longest claim (most detail)
        representative = max(group_claims, key=lambda c: len(c.text)).text

        cg = ClaimGroup(
            representative=representative,
            claims=group_claims,
            providers_supporting=providers_in_group,
            agreement_score=round(agreement, 3),
            claim_type=claim_type,
        )

        if n_providers >= min_providers_for_consensus:
            cg.is_contested, cg.contradiction_note = _is_contradictory(cg)
            if cg.is_contested:
                contested_groups.append(cg)
            else:
                consensus_groups.append(cg)
        else:
            unique_groups.append(cg)

    consensus_groups.sort(key=lambda g: g.agreement_score, reverse=True)
    contested_groups.sort(key=lambda g: g.agreement_score, reverse=True)

    # Overall agreement rate: fraction of claim instances in consensus groups
    total_instances = sum(len(g.claims) for g in consensus_groups + contested_groups + unique_groups)
    consensus_instances = sum(len(g.claims) for g in consensus_groups)
    overall_rate = consensus_instances / max(total_instances, 1)

    return ConsensusResult(
        total_providers=total_providers,
        consensus_groups=consensus_groups,
        contested_groups=contested_groups,
        unique_groups=unique_groups,
        provider_agreement_matrix=agreement_matrix,
        overall_agreement_rate=round(overall_rate, 3),
    )
