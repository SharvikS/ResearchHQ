"""Tests for ensemble/confidence.py — multi-dimensional confidence scoring."""

from __future__ import annotations

import pytest

from researchhq.ensemble.claim_extractor import Claim
from researchhq.ensemble.confidence import ConfidenceReport, score_confidence
from researchhq.ensemble.consensus import ConsensusResult, ClaimGroup, analyze_consensus
from researchhq.ensemble.orchestrator import EnsembleRun, ProviderResult


def _make_run(
    successes: list[str] = None,
    failures: list[str] = None,
) -> EnsembleRun:
    results: list[ProviderResult] = []
    for p in (successes or []):
        results.append(ProviderResult(
            provider=p, model="m", text="some text output",
            status="success", input_tokens=100, output_tokens=200,
        ))
    for p in (failures or []):
        results.append(ProviderResult(
            provider=p, model="", text="",
            status="error", error="api error",
        ))
    return EnsembleRun(query="test", results=results)


def _make_consensus(
    n_consensus: int = 3,
    n_contested: int = 0,
    n_unique: int = 0,
    total_providers: int = 3,
) -> ConsensusResult:
    def _group(n: int, prefix: str) -> list[ClaimGroup]:
        groups = []
        for i in range(n):
            c = Claim(text=f"{prefix} claim {i}", provider="groq")
            groups.append(ClaimGroup(
                representative=f"{prefix} claim {i}",
                claims=[c],
                providers_supporting=["groq"],
                agreement_score=0.7,
            ))
        return groups

    return ConsensusResult(
        total_providers=total_providers,
        consensus_groups=_group(n_consensus, "consensus"),
        contested_groups=_group(n_contested, "contested"),
        unique_groups=_group(n_unique, "unique"),
        overall_agreement_rate=n_consensus / max(n_consensus + n_contested + n_unique, 1),
    )


class _MockSource:
    def __init__(self, tier_value: str = "news", url: str = "https://example.com"):
        self.url = url

        class _Tier:
            def __init__(self, v):
                self.value = v
        self.tier = _Tier(tier_value)


# ── Basic output shape ─────────────────────────────────────────────────────────

def test_returns_confidence_report():
    run = _make_run(successes=["groq", "gemini"])
    consensus = _make_consensus()
    report = score_confidence(run, consensus, [])
    assert isinstance(report, ConfidenceReport)


def test_overall_score_in_range():
    run = _make_run(successes=["groq", "gemini", "openai"])
    consensus = _make_consensus(n_consensus=5)
    report = score_confidence(run, consensus, [])
    assert 0.0 <= report.overall_score <= 1.0


def test_confidence_label_high():
    run = _make_run(successes=["groq", "gemini", "openai"])
    consensus = _make_consensus(n_consensus=10, n_contested=0)
    sources = [_MockSource("official")] * 5
    report = score_confidence(run, consensus, sources)
    assert report.overall_score >= 0.6
    assert report.confidence_label in ("high", "medium")


def test_confidence_label_low_all_fail():
    run = _make_run(failures=["groq", "gemini"])
    consensus = _make_consensus(n_consensus=0, n_unique=5)
    report = score_confidence(run, consensus, [])
    assert report.overall_score < 0.6
    assert report.confidence_label in ("low", "medium")


# ── Component scores ──────────────────────────────────────────────────────────

def test_source_quality_score_with_high_tier():
    run = _make_run(successes=["groq"])
    consensus = _make_consensus()
    sources = [_MockSource("official"), _MockSource("academic")]
    report = score_confidence(run, consensus, sources)
    assert report.source_quality_score > 0.8


def test_source_quality_score_no_sources():
    run = _make_run(successes=["groq"])
    consensus = _make_consensus()
    report = score_confidence(run, consensus, [])
    assert report.source_quality_score == pytest.approx(0.30, abs=0.05)


def test_factual_consistency_penalised_by_contested():
    run = _make_run(successes=["groq", "gemini"])
    # All contested → low consistency
    consensus = _make_consensus(n_consensus=0, n_contested=5, n_unique=0)
    report = score_confidence(run, consensus, [])
    assert report.factual_consistency_score < 0.5


def test_factual_consistency_high_no_contested():
    run = _make_run(successes=["groq", "gemini"])
    consensus = _make_consensus(n_consensus=5, n_contested=0)
    report = score_confidence(run, consensus, [])
    assert report.factual_consistency_score >= 0.9


def test_hallucination_risk_high_when_all_unique():
    run = _make_run(successes=["groq"])
    consensus = _make_consensus(n_consensus=0, n_unique=10)
    report = score_confidence(run, consensus, [])
    assert report.hallucination_risk > 0.3


def test_provider_agreement_score_all_succeed():
    run = _make_run(successes=["groq", "gemini", "openai"])
    consensus = _make_consensus(n_consensus=5, total_providers=3)
    report = score_confidence(run, consensus, [])
    assert report.provider_agreement_score > 0.5


def test_provider_agreement_score_all_fail():
    run = _make_run(failures=["groq", "gemini"])
    consensus = _make_consensus(n_consensus=0)
    report = score_confidence(run, consensus, [])
    assert report.provider_agreement_score == pytest.approx(0.0, abs=0.1)


# ── Breakdown ─────────────────────────────────────────────────────────────────

def test_breakdown_sums_to_overall():
    run = _make_run(successes=["groq", "gemini"])
    consensus = _make_consensus()
    sources = [_MockSource("news")]
    report = score_confidence(run, consensus, sources)
    breakdown_sum = sum(report.breakdown.values())
    assert abs(breakdown_sum - report.overall_score) < 0.02


# ── Uncertainty notes ─────────────────────────────────────────────────────────

def test_uncertainty_note_for_failed_providers():
    run = _make_run(successes=["groq"], failures=["gemini"])
    consensus = _make_consensus()
    report = score_confidence(run, consensus, [])
    assert any("failed" in n.lower() or "gemini" in n for n in report.uncertainty_notes)


def test_uncertainty_note_for_contested_claims():
    run = _make_run(successes=["groq", "gemini"])
    consensus = _make_consensus(n_contested=3)
    report = score_confidence(run, consensus, [])
    assert any("contested" in n.lower() for n in report.uncertainty_notes)
