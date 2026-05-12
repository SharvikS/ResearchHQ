"""Mode-aware verifier rule tests.

Each test fails on a specific reliability bug:
- high-confidence claim with no high-tier source
- news single-source claim not flagged unconfirmed
- market figure without date or attribution
- academic claim without paper-level reference
"""

from researchhq.agents.citation_guard import CitationViolation
from researchhq.agents.verifier import (
    rule_academic_paper_attribution,
    rule_high_conf_needs_high_tier,
    rule_market_dated_attribution,
    rule_news_multi_source,
    rule_no_citation_violations,
    verify,
)
from researchhq.modes import get_mode
from researchhq.reports.schema import Fact, Section
from researchhq.search.source_quality import RankedSource, SourceTier


def _src(url: str, tier: SourceTier, score: int = 8, domain: str | None = None) -> RankedSource:
    host = domain or url.split("//")[-1].split("/")[0]
    return RankedSource(url=url, title="t", snippet="s", tier=tier, score=score, domain=host)


# ---------- shared rules ----------

def test_high_conf_without_high_tier_fails():
    facts = [Fact(claim="X", evidence_urls=["https://reddit.com/x"], confidence=0.9)]
    sources = [_src("https://reddit.com/x", SourceTier.COMMUNITY)]
    r = rule_high_conf_needs_high_tier(facts=facts, sources=sources)
    assert not r.passed
    assert r.severity == "fail"


def test_high_conf_with_news_source_passes():
    facts = [Fact(claim="X", evidence_urls=["https://bbc.com/x"], confidence=0.9)]
    sources = [_src("https://bbc.com/x", SourceTier.NEWS)]
    r = rule_high_conf_needs_high_tier(facts=facts, sources=sources)
    assert r.passed


def test_invented_citations_fail_rule():
    violations = [CitationViolation(kind="extractor.unknown_url", location="X", url="https://fake")]
    r = rule_no_citation_violations(violations=violations)
    assert not r.passed
    assert r.severity == "fail"


# ---------- news mode ----------

def test_news_single_source_high_conf_fails():
    facts = [
        Fact(claim="OpenAI launched X", evidence_urls=["https://bbc.com/a"], confidence=0.9),
    ]
    sources = [_src("https://bbc.com/a", SourceTier.NEWS, domain="bbc.com")]
    r = rule_news_multi_source(facts=facts, sources=sources)
    assert not r.passed
    assert "single-source" in r.message.lower() or "unconfirmed" in r.message.lower()


def test_news_multi_source_high_conf_passes():
    facts = [
        Fact(
            claim="OpenAI launched X",
            evidence_urls=["https://bbc.com/a", "https://reuters.com/b"],
            confidence=0.9,
        ),
    ]
    sources = [
        _src("https://bbc.com/a", SourceTier.NEWS, domain="bbc.com"),
        _src("https://reuters.com/b", SourceTier.NEWS, domain="reuters.com"),
    ]
    r = rule_news_multi_source(facts=facts, sources=sources)
    assert r.passed


def test_news_low_conf_claim_not_evaluated():
    facts = [Fact(claim="rumor", evidence_urls=["https://bbc.com/a"], confidence=0.5)]
    sources = [_src("https://bbc.com/a", SourceTier.NEWS, domain="bbc.com")]
    r = rule_news_multi_source(facts=facts, sources=sources)
    assert r.passed  # not high-confidence => not subject to multi-source rule


# ---------- market mode ----------

def test_market_figure_without_date_fails():
    facts = [Fact(claim="The market is worth $50 billion", evidence_urls=[], confidence=0.5)]
    r = rule_market_dated_attribution(facts=facts, sections=[])
    assert not r.passed


def test_market_figure_with_year_passes():
    facts = [Fact(claim="The market is worth $50 billion in 2026", evidence_urls=[], confidence=0.5)]
    r = rule_market_dated_attribution(facts=facts, sections=[])
    assert r.passed


def test_market_figure_with_attribution_passes():
    facts = [Fact(claim="According to Gartner the market is $50 billion", evidence_urls=[], confidence=0.5)]
    r = rule_market_dated_attribution(facts=facts, sections=[])
    assert r.passed


def test_market_section_body_also_checked():
    sections = [Section(heading="Market overview", body="The TAM is 50 billion dollars.")]
    r = rule_market_dated_attribution(facts=[], sections=sections)
    assert not r.passed


# ---------- academic mode ----------

def test_academic_high_conf_without_academic_source_fails():
    facts = [Fact(claim="RAG outperforms baselines (et al.)", evidence_urls=["https://blog.example/x"], confidence=0.9)]
    sources = [_src("https://blog.example/x", SourceTier.BLOG)]
    r = rule_academic_paper_attribution(facts=facts, sources=sources)
    assert not r.passed


def test_academic_with_paper_ref_and_arxiv_source_passes():
    facts = [Fact(claim="Lewis et al. evaluated RAG benchmarks", evidence_urls=["https://arxiv.org/abs/2005.11401"], confidence=0.9)]
    sources = [_src("https://arxiv.org/abs/2005.11401", SourceTier.ACADEMIC)]
    r = rule_academic_paper_attribution(facts=facts, sources=sources)
    assert r.passed


# ---------- end-to-end verifier ----------

def test_verify_includes_news_rule_only_in_news_mode():
    facts = [Fact(claim="X", evidence_urls=["https://bbc.com/a"], confidence=0.9)]
    sources = [_src("https://bbc.com/a", SourceTier.NEWS, domain="bbc.com")]
    note_topic = verify(get_mode("topic"), sources, facts)
    note_news = verify(get_mode("news"), sources, facts)
    rule_names_topic = {r.name for r in note_topic.rules}
    rule_names_news = {r.name for r in note_news.rules}
    assert "news.multi_source_corroboration" not in rule_names_topic
    assert "news.multi_source_corroboration" in rule_names_news


def test_verify_propagates_violations_into_note():
    facts = [Fact(claim="X", evidence_urls=["https://bbc.com/a"], confidence=0.9)]
    sources = [
        _src("https://bbc.com/a", SourceTier.NEWS, domain="bbc.com"),
        _src("https://reuters.com/b", SourceTier.NEWS, domain="reuters.com"),
        _src("https://wsj.com/c", SourceTier.NEWS, domain="wsj.com"),
    ]
    violations = [CitationViolation(kind="synth.unknown_url", location="Findings", url="https://fake")]
    note = verify(get_mode("topic"), sources, facts, violations=violations)
    assert any(v.kind == "synth.unknown_url" for v in note.violations)
    failed = [r for r in note.rules if not r.passed]
    assert any(r.name == "citations.all_known_urls" for r in failed)
