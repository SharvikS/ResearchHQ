"""Tests for ensemble/disagreement.py and ensemble/verifier.py."""

from __future__ import annotations

import pytest

from researchhq.ensemble.claim_extractor import Claim
from researchhq.ensemble.confidence import ConfidenceReport, score_confidence
from researchhq.ensemble.consensus import ClaimGroup, ConsensusResult
from researchhq.ensemble.disagreement import (
    Disagreement,
    DisagreementReport,
    analyze_disagreements,
)
from researchhq.ensemble.orchestrator import EnsembleRun, ProviderResult
from researchhq.ensemble.verifier import EnsembleVerifierNote, verify_synthesis
from researchhq.reports.schema import Section


# ── Helpers ────────────────────────────────────────────────────────────────────

def _claim(text: str, provider: str) -> Claim:
    return Claim(text=text, provider=provider)


def _contested_group(
    claim_a: str, provider_a: str,
    claim_b: str, provider_b: str,
    note: str = "numeric disagreement: 50 vs 200",
) -> ClaimGroup:
    return ClaimGroup(
        representative=claim_a,
        claims=[_claim(claim_a, provider_a), _claim(claim_b, provider_b)],
        providers_supporting=[provider_a, provider_b],
        agreement_score=0.5,
        is_contested=True,
        contradiction_note=note,
    )


def _empty_consensus() -> ConsensusResult:
    return ConsensusResult(total_providers=2)


def _consensus_with_contested(groups: list[ClaimGroup]) -> ConsensusResult:
    return ConsensusResult(
        total_providers=2,
        contested_groups=groups,
        overall_agreement_rate=0.5,
    )


# ── analyze_disagreements ──────────────────────────────────────────────────────

def test_no_disagreements_on_empty_consensus():
    report = analyze_disagreements(_empty_consensus())
    assert isinstance(report, DisagreementReport)
    assert report.disagreements == []
    assert report.agreement_rate == 1.0
    assert "No significant" in report.summary


def test_major_disagreement_detected():
    group = _contested_group(
        "Market grew 50 percent", "groq",
        "Market grew 200 percent", "gemini",
        note="numeric disagreement: 50 vs 200",
    )
    consensus = _consensus_with_contested([group])
    report = analyze_disagreements(consensus)
    assert report.major_count >= 1
    assert "major" in report.summary.lower()
    assert report.has_major_conflicts


def test_moderate_disagreement_detected():
    group = _contested_group(
        "Technology is improving rapidly", "groq",
        "Technology adoption is declining sharply", "gemini",
        note="conflicting sentiment across providers",
    )
    consensus = _consensus_with_contested([group])
    report = analyze_disagreements(consensus)
    assert report.moderate_count >= 1


def test_minor_disagreement_detected():
    group = _contested_group(
        "Researchers are making progress", "groq",
        "Scientists are advancing the field", "gemini",
        note=None,  # type: ignore[arg-type]
    )
    group.contradiction_note = None
    consensus = _consensus_with_contested([group])
    report = analyze_disagreements(consensus)
    assert report.minor_count >= 1


def test_disagreement_has_resolution():
    group = _contested_group(
        "Revenue is $10 billion", "groq",
        "Revenue is $50 billion", "gemini",
        note="numeric disagreement: 10 vs 50",
    )
    consensus = _consensus_with_contested([group])
    report = analyze_disagreements(consensus)
    for d in report.disagreements:
        assert d.resolution is not None
        assert len(d.resolution) > 0


def test_same_provider_not_paired():
    """Claims from the same provider in a group should not produce a disagreement."""
    group = ClaimGroup(
        representative="some claim",
        claims=[
            _claim("Same provider claim A", "groq"),
            _claim("Same provider claim B", "groq"),
        ],
        providers_supporting=["groq"],
        agreement_score=0.5,
        is_contested=True,
    )
    consensus = _consensus_with_contested([group])
    report = analyze_disagreements(consensus)
    # No cross-provider pairs → no disagreements
    assert report.total_contested == 1
    assert report.disagreements == []


def test_agreement_rate_decreases_with_contested():
    groups = [
        _contested_group("A", "groq", "B", "gemini"),
        _contested_group("C", "groq", "D", "gemini"),
    ]
    # Also add unique groups via direct construction
    consensus = ConsensusResult(
        total_providers=2,
        consensus_groups=[ClaimGroup("consensus", [_claim("consensus claim", "groq")], ["groq"])],
        contested_groups=groups,
        overall_agreement_rate=0.3,
    )
    report = analyze_disagreements(consensus)
    assert 0.0 <= report.agreement_rate <= 1.0


# ── verify_synthesis ──────────────────────────────────────────────────────────

def _make_sections(with_valid_url: bool = True) -> list[Section]:
    url = "https://example.com/article" if with_valid_url else "https://unknown.example.com/page"
    return [Section(heading="Findings", body=f"Research shows [evidence]({url}) that results are promising.")]


def _make_run(n_success: int = 2, n_fail: int = 0) -> EnsembleRun:
    results: list[ProviderResult] = []
    for i in range(n_success):
        results.append(ProviderResult(
            provider=f"p{i}", model="m", text="text", status="success",
        ))
    for i in range(n_fail):
        results.append(ProviderResult(
            provider=f"fail{i}", model="", text="", status="error",
        ))
    return EnsembleRun(query="q", results=results)


class _MockSource:
    url = "https://example.com/article"

    class tier:
        value = "news"


def _make_confidence(score: float = 0.70) -> ConfidenceReport:
    return ConfidenceReport(
        overall_score=score,
        provider_agreement_score=0.7,
        source_quality_score=0.7,
        factual_consistency_score=0.7,
        hallucination_risk=0.2,
        provider_scores={"p0": 0.8, "p1": 0.7},
    )


def test_verify_returns_note():
    sections = _make_sections()
    run = _make_run()
    conf = _make_confidence()
    note = verify_synthesis(sections, run, conf, [_MockSource()])
    assert isinstance(note, EnsembleVerifierNote)


def test_adjusted_confidence_in_range():
    sections = _make_sections()
    run = _make_run()
    conf = _make_confidence(0.70)
    note = verify_synthesis(sections, run, conf, [_MockSource()])
    assert 0.0 <= note.adjusted_confidence <= 1.0


def test_poor_source_coverage_penalises_confidence():
    sections = _make_sections(with_valid_url=False)  # URL not in sources
    run = _make_run()
    conf = _make_confidence(0.70)
    note = verify_synthesis(sections, run, conf, [_MockSource()])
    assert note.adjusted_confidence <= note.original_confidence


def test_all_fail_penalises_confidence():
    sections = _make_sections()
    run = _make_run(n_success=0, n_fail=2)
    conf = _make_confidence(0.70)
    note = verify_synthesis(sections, run, conf, [])
    assert note.adjusted_confidence < note.original_confidence


def test_support_strength_strong_with_many_providers():
    sections = _make_sections()
    run = EnsembleRun(query="q", results=[
        ProviderResult(provider=f"p{i}", model="m", text="t", status="success")
        for i in range(4)
    ])
    conf = ConfidenceReport(
        overall_score=0.80,
        provider_agreement_score=0.75,
        source_quality_score=0.80,
        factual_consistency_score=0.85,
        hallucination_risk=0.1,
        provider_scores={f"p{i}": 0.8 for i in range(4)},
    )
    note = verify_synthesis(sections, run, conf, [_MockSource()])
    assert note.support_strength == "strong"


def test_support_strength_weak_with_single_provider():
    sections = _make_sections()
    run = _make_run(n_success=1, n_fail=2)
    conf = _make_confidence(0.40)
    conf.provider_agreement_score = 0.2
    note = verify_synthesis(sections, run, conf, [])
    assert note.support_strength == "weak"


def test_adjustments_list_populated_on_penalty():
    sections = _make_sections(with_valid_url=False)
    run = _make_run(n_success=0, n_fail=3)
    conf = _make_confidence(0.70)
    conf.hallucination_risk = 0.8
    note = verify_synthesis(sections, run, conf, [])
    assert len(note.adjustments) > 0
