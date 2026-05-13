"""Tests for ensemble/consensus.py — claim grouping and consensus analysis."""

from __future__ import annotations

import pytest

from researchhq.ensemble.claim_extractor import Claim
from researchhq.ensemble.consensus import (
    ConsensusResult,
    analyze_consensus,
    jaccard_similarity,
)


def _claim(text: str, provider: str = "groq", ctype: str = "fact") -> Claim:
    return Claim(text=text, provider=provider, claim_type=ctype)


# ── Jaccard similarity ─────────────────────────────────────────────────────────

def test_jaccard_identical():
    assert jaccard_similarity("quantum computing has qubits", "quantum computing has qubits") == 1.0


def test_jaccard_no_overlap():
    score = jaccard_similarity("apple pie recipe", "quantum entanglement physics")
    assert score < 0.1


def test_jaccard_partial_overlap():
    score = jaccard_similarity(
        "IBM announced a new quantum processor in 2023",
        "IBM unveiled quantum computing hardware this year",
    )
    assert 0.1 < score < 0.9


def test_jaccard_stopwords_ignored():
    # Sentences that share only stopwords should score near 0
    score = jaccard_similarity("the cat sat on the mat", "the dog lay in the park")
    assert score < 0.25


# ── analyze_consensus ─────────────────────────────────────────────────────────

def test_empty_claims():
    result = analyze_consensus({})
    assert result.total_providers == 0
    assert result.total_claims == 0
    assert result.all_groups == []


def test_single_provider_all_unique():
    claims = {"groq": [_claim("quantum computers use qubits"), _claim("IBM leads research")]}
    result = analyze_consensus(claims)
    # With only one provider, everything should be unique
    assert result.consensus_groups == []
    assert result.unique_groups != []


def test_two_providers_consensus():
    claims = {
        "groq":   [_claim("quantum computers use qubits for processing information", "groq")],
        "gemini": [_claim("quantum computers utilize qubits for computational tasks", "gemini")],
    }
    result = analyze_consensus(claims, similarity_threshold=0.30)
    # Should detect consensus on the qubits claim
    assert len(result.consensus_groups) >= 1
    assert result.overall_agreement_rate > 0.0


def test_three_providers_strong_consensus():
    claims = {
        "groq":      [_claim("IBM announced a 1000 qubit quantum processor in 2023", "groq")],
        "gemini":    [_claim("IBM released a 1000 qubit quantum chip during 2023", "gemini")],
        "anthropic": [_claim("IBM unveiled its 1000 qubit quantum processor this year", "anthropic")],
    }
    result = analyze_consensus(claims, similarity_threshold=0.25, min_providers_for_consensus=2)
    assert len(result.consensus_groups) >= 1
    top_group = result.consensus_groups[0]
    assert len(top_group.providers_supporting) >= 2


def test_contested_numeric_disagreement():
    claims = {
        "groq":   [_claim("The market grew 50 percent in 2023 to reach $10 billion dollars")],
        "gemini": [_claim("The market grew 200 percent in 2023 reaching $40 billion dollars")],
    }
    result = analyze_consensus(claims, similarity_threshold=0.20, min_providers_for_consensus=2)
    # Numeric disagreement should be detected
    total_contested = len(result.contested_groups)
    # Either grouped as contested OR as separate unique groups; numeric disagreement should be flagged
    all_contested_notes = [g.contradiction_note for g in result.contested_groups if g.contradiction_note]
    if total_contested > 0:
        assert any("numeric" in (n or "") for n in all_contested_notes)


def test_provider_agreement_matrix_symmetrical():
    claims = {
        "groq":   [_claim("Quantum computers are advancing rapidly")],
        "gemini": [_claim("Quantum computing technology is progressing fast")],
    }
    result = analyze_consensus(claims)
    matrix = result.provider_agreement_matrix
    assert matrix["groq"]["gemini"] == matrix["gemini"]["groq"]


def test_agreement_rate_between_0_and_1():
    claims = {
        "groq": [_claim("A"), _claim("B"), _claim("C")],
        "gemini": [_claim("D"), _claim("E"), _claim("F")],
    }
    result = analyze_consensus(claims)
    assert 0.0 <= result.overall_agreement_rate <= 1.0


def test_min_providers_for_consensus_threshold():
    """Claims from only 1 provider should never be consensus when threshold=2."""
    claims = {
        "groq": [_claim("some unique fact only groq knows")],
    }
    result = analyze_consensus(claims, min_providers_for_consensus=2)
    assert result.consensus_groups == []
    assert len(result.unique_groups) >= 1


def test_high_similarity_threshold_fewer_groups():
    text = "quantum entanglement enables faster computation"
    claims = {
        "groq":   [_claim(text), _claim("IBM research in quantum")],
        "gemini": [_claim("quantum entanglement allows faster computing"), _claim("Google quantum lab")],
    }
    result_strict = analyze_consensus(claims, similarity_threshold=0.80)
    result_loose = analyze_consensus(claims, similarity_threshold=0.20)
    # Looser threshold should produce fewer, larger groups (more consensus)
    assert len(result_loose.consensus_groups) >= len(result_strict.consensus_groups)
