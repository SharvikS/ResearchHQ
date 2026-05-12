"""Citation guard: deterministic URL validation tests."""

from researchhq.agents.citation_guard import (
    strip_unknown_citations,
    validate_evidence_urls,
)
from researchhq.reports.schema import Fact


KNOWN = ["https://arxiv.org/abs/1", "https://www.bbc.com/x"]


def test_validate_drops_invented_urls_from_evidence():
    facts = [
        Fact(claim="A", evidence_urls=["https://arxiv.org/abs/1", "https://invented.example/foo"], confidence=0.9),
    ]
    cleaned, violations = validate_evidence_urls(facts, KNOWN)
    assert cleaned[0].evidence_urls == ["https://arxiv.org/abs/1"]
    assert len(violations) == 1
    assert violations[0].kind == "extractor.unknown_url"
    assert violations[0].url == "https://invented.example/foo"


def test_validate_demotes_high_conf_when_no_valid_evidence():
    facts = [
        Fact(claim="A", evidence_urls=["https://invented.example/foo"], confidence=0.9),
    ]
    cleaned, violations = validate_evidence_urls(facts, KNOWN)
    assert cleaned[0].confidence == 0.5
    assert any(v.kind == "extractor.no_evidence" for v in violations)


def test_validate_keeps_low_conf_facts_without_evidence_unchanged():
    facts = [Fact(claim="A", evidence_urls=[], confidence=0.4)]
    cleaned, violations = validate_evidence_urls(facts, KNOWN)
    assert cleaned[0].confidence == 0.4
    assert violations == []


def test_validate_normalizes_trailing_slash():
    facts = [Fact(claim="A", evidence_urls=["https://www.bbc.com/x/"], confidence=0.9)]
    cleaned, violations = validate_evidence_urls(facts, KNOWN)
    assert cleaned[0].evidence_urls == ["https://www.bbc.com/x/"]
    assert violations == []


def test_strip_unknown_citations_replaces_invented_links():
    md = "See [Paper](https://arxiv.org/abs/1) and [Made up](https://fake.example/x)."
    out, violations = strip_unknown_citations(md, KNOWN, location="Findings")
    assert "(https://arxiv.org/abs/1)" in out
    assert "https://fake.example/x" not in out
    assert "[Made up]" in out  # text retained, URL stripped
    assert len(violations) == 1
    assert violations[0].kind == "synth.unknown_url"
    assert violations[0].location == "Findings"


def test_strip_handles_anchor_only_refs():
    md = "[link](#foo) and [contact](mailto:x@y)."
    out, violations = strip_unknown_citations(md, KNOWN)
    assert "(#foo)" not in out
    assert "(mailto:" not in out
    assert violations == []


def test_strip_keeps_known_citations_intact():
    md = "[BBC](https://www.bbc.com/x) reports."
    out, violations = strip_unknown_citations(md, KNOWN)
    assert out == "[BBC](https://www.bbc.com/x) reports."
    assert violations == []
