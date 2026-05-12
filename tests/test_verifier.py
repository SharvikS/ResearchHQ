from researchhq.agents.verifier import verify
from researchhq.modes import get_mode
from researchhq.reports.schema import Fact
from researchhq.search.source_quality import RankedSource, SourceTier


def _src(url: str, tier: SourceTier, score: int = 8, domain: str | None = None) -> RankedSource:
    return RankedSource(
        url=url, title="t", snippet="s", tier=tier, score=score, domain=domain or url.split("//")[-1].split("/")[0]
    )


def test_verify_zero_when_no_sources():
    note = verify(get_mode("topic"), [], [])
    assert note.overall_confidence == 0.0


def test_high_tier_mix_yields_higher_confidence_than_low_tier_only():
    mode = get_mode("topic")
    high = [
        _src("https://arxiv.org/a", SourceTier.ACADEMIC, 12, "arxiv.org"),
        _src("https://www.bbc.com/x", SourceTier.NEWS, 9, "bbc.com"),
        _src("https://docs.example.com/x", SourceTier.DOCS, 8, "docs.example.com"),
    ]
    low = [
        _src("https://www.reddit.com/a", SourceTier.COMMUNITY, 5, "reddit.com"),
        _src("https://twitter.com/x", SourceTier.SOCIAL, 4, "twitter.com"),
    ]
    facts = [Fact(claim="x", evidence_urls=["https://arxiv.org/a"], confidence=0.9)]
    h_note = verify(mode, high, facts)
    l_note = verify(mode, low, [Fact(claim="x", evidence_urls=[], confidence=0.4)])
    assert h_note.overall_confidence > l_note.overall_confidence


def test_single_domain_penalty_applied():
    mode = get_mode("topic")
    same_domain = [
        _src("https://example.com/a", SourceTier.NEWS, 8, "example.com"),
        _src("https://example.com/b", SourceTier.NEWS, 8, "example.com"),
        _src("https://example.com/c", SourceTier.NEWS, 8, "example.com"),
    ]
    note = verify(mode, same_domain, [])
    assert any("domain" in n.lower() for n in note.notes)
