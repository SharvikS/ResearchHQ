"""Tests for ensemble/claim_extractor.py — claim extraction from text."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from researchhq.ensemble.claim_extractor import (
    Claim,
    extract_claims,
    extract_claims_heuristic,
    extract_all_claims,
)
from researchhq.ensemble.orchestrator import ProviderResult
from researchhq.llm.providers.base import LLMResponse


SAMPLE_TEXT = """
## Quantum Computing Advances

IBM announced a 1000-qubit quantum processor in November 2023, setting a new record.
This breakthrough represents a 50% increase in qubit count over the previous year.
Google's quantum division published related research on error correction in 2023.

Researchers recommend investing in quantum-safe cryptography now.
In conclusion, quantum computing is poised for commercial applications by 2026.
"""


# ── Heuristic extraction ───────────────────────────────────────────────────────

def test_extract_returns_list_of_claims():
    claims = extract_claims_heuristic(SAMPLE_TEXT, "test_provider")
    assert isinstance(claims, list)
    assert all(isinstance(c, Claim) for c in claims)


def test_extract_finds_multiple_claims():
    claims = extract_claims_heuristic(SAMPLE_TEXT, "groq")
    assert len(claims) >= 3


def test_claims_have_provider_set():
    claims = extract_claims_heuristic(SAMPLE_TEXT, "groq")
    assert all(c.provider == "groq" for c in claims)


def test_short_fragments_filtered():
    # Single words or very short strings should produce no claims
    claims = extract_claims_heuristic("Yes. No. OK.", "groq")
    assert len(claims) == 0


def test_has_number_detected():
    claims = extract_claims_heuristic(
        "The market grew by 50% to reach $2 billion in revenue.", "groq"
    )
    numeric_claims = [c for c in claims if c.has_number]
    assert len(numeric_claims) >= 1


def test_has_date_detected():
    claims = extract_claims_heuristic(
        "IBM announced its processor in November 2023.", "groq"
    )
    date_claims = [c for c in claims if c.has_date]
    assert len(date_claims) >= 1


def test_claim_type_recommendation():
    claims = extract_claims_heuristic(
        "Experts recommend using quantum-safe algorithms now.", "groq"
    )
    rec_claims = [c for c in claims if c.claim_type == "recommendation"]
    assert len(rec_claims) >= 1


def test_claim_type_conclusion():
    claims = extract_claims_heuristic(
        "In conclusion, quantum computing will transform industries.", "groq"
    )
    conc_claims = [c for c in claims if c.claim_type == "conclusion"]
    assert len(conc_claims) >= 1


def test_claim_type_statistic():
    claims = extract_claims_heuristic(
        "Revenue grew by 150 percent year over year.", "groq"
    )
    stat_claims = [c for c in claims if c.claim_type == "statistic"]
    assert len(stat_claims) >= 1


def test_confidence_in_valid_range():
    claims = extract_claims_heuristic(SAMPLE_TEXT, "groq")
    for c in claims:
        assert 0.0 <= c.confidence <= 1.0


def test_url_in_source_mentions():
    text = "IBM research at https://research.ibm.com confirmed new results."
    claims = extract_claims_heuristic(text, "groq")
    url_claims = [c for c in claims if c.source_mentions]
    assert len(url_claims) >= 1


def test_markdown_stripped():
    text = "## Big Heading\n**Important:** The processor has 1000 qubits in 2023."
    claims = extract_claims_heuristic(text, "groq")
    for c in claims:
        assert "##" not in c.text
        assert "**" not in c.text


# ── Public extract_claims alias ────────────────────────────────────────────────

def test_extract_claims_is_heuristic():
    claims1 = extract_claims(SAMPLE_TEXT, "groq")
    claims2 = extract_claims_heuristic(SAMPLE_TEXT, "groq")
    assert len(claims1) == len(claims2)


# ── extract_all_claims ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_all_claims_groups_by_provider():
    results = [
        ProviderResult(provider="groq", model="m", text=SAMPLE_TEXT, status="success"),
        ProviderResult(provider="gemini", model="m", text=SAMPLE_TEXT, status="success"),
    ]
    claims_map = await extract_all_claims(results, use_llm=False)
    assert set(claims_map.keys()) == {"groq", "gemini"}
    assert all(len(v) > 0 for v in claims_map.values())


@pytest.mark.asyncio
async def test_extract_all_claims_llm_fallback_on_bad_json():
    """If LLM returns bad JSON, should fall back to heuristic."""
    mock_router = MagicMock()
    mock_router.complete = AsyncMock(return_value=LLMResponse(
        text="not valid json at all !!!",
        model="m", provider="groq", input_tokens=10, output_tokens=5,
    ))

    results = [
        ProviderResult(provider="groq", model="m", text=SAMPLE_TEXT, status="success"),
    ]
    claims_map = await extract_all_claims(results, router=mock_router, use_llm=True)
    assert "groq" in claims_map
    # Should have fallen back to heuristic
    assert len(claims_map["groq"]) > 0


@pytest.mark.asyncio
async def test_extract_all_claims_llm_success():
    """Valid JSON from LLM should produce structured claims."""
    valid_response = json.dumps([
        {"claim": "IBM has 1000 qubits", "type": "fact", "confidence": 0.9,
         "has_number": True, "has_date": False, "topics": ["quantum"]},
        {"claim": "Research advances rapidly", "type": "conclusion", "confidence": 0.7,
         "has_number": False, "has_date": False, "topics": ["research"]},
    ])
    mock_router = MagicMock()
    mock_router.complete = AsyncMock(return_value=LLMResponse(
        text=valid_response,
        model="m", provider="groq", input_tokens=100, output_tokens=50,
    ))

    results = [
        ProviderResult(provider="groq", model="m", text=SAMPLE_TEXT, status="success"),
    ]
    claims_map = await extract_all_claims(results, router=mock_router, use_llm=True)
    claims = claims_map["groq"]
    assert len(claims) == 2
    assert claims[0].claim_type == "fact"
    assert claims[0].has_number is True
    assert claims[1].claim_type == "conclusion"
