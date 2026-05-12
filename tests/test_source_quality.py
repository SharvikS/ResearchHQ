from researchhq.search.source_quality import (
    SourceTier,
    classify,
    rank_sources,
)


def test_classify_known_tiers():
    assert classify("https://arxiv.org/abs/2301.12345") is SourceTier.ACADEMIC
    assert classify("https://www.nasa.gov/foo") is SourceTier.GOVERNMENT
    assert classify("https://stanford.edu/~prof/paper") is SourceTier.ACADEMIC
    assert classify("https://www.bbc.com/news/x") is SourceTier.NEWS
    assert classify("https://github.com/foo/bar") is SourceTier.GITHUB
    assert classify("https://www.reddit.com/r/x") is SourceTier.COMMUNITY
    assert classify("https://www.g2.com/products/x") is SourceTier.COMPARISON
    assert classify("https://en.wikipedia.org/wiki/X") is SourceTier.WIKI
    assert classify("https://duckduckgo.com/?q=test") is SourceTier.SEARCH_ENGINE


def test_classify_subject_owned_domain():
    assert classify("https://supabase.com/pricing", subject="Supabase") is SourceTier.OFFICIAL
    assert classify("https://docs.supabase.com/api", subject="Supabase") is SourceTier.DOCS


def test_rank_sources_orders_by_score_and_drops_search_engines():
    raw = [
        ("https://duckduckgo.com/?q=foo", "ddg", "search engine"),
        ("https://www.reddit.com/r/x", "reddit", "community"),
        ("https://arxiv.org/abs/1", "paper", "academic"),
        ("https://www.bbc.com/n", "bbc", "news"),
    ]
    ranked = rank_sources(raw, subject="foo")
    # search engine dropped
    assert all(s.tier is not SourceTier.SEARCH_ENGINE for s in ranked)
    # academic + news rank above community
    tiers = [s.tier for s in ranked]
    assert tiers.index(SourceTier.ACADEMIC) < tiers.index(SourceTier.COMMUNITY)
    assert tiers.index(SourceTier.NEWS) < tiers.index(SourceTier.COMMUNITY)


def test_rank_sources_dedupes_urls():
    raw = [
        ("https://github.com/x/y", "a", ""),
        ("https://github.com/x/y", "a-dup", ""),
    ]
    ranked = rank_sources(raw)
    assert len(ranked) == 1


def test_rank_sources_respects_drop_tiers():
    raw = [
        ("https://github.com/x/y", "a", ""),
        ("https://twitter.com/foo", "tweet", ""),
    ]
    ranked = rank_sources(raw, drop_tiers={SourceTier.SEARCH_ENGINE, SourceTier.SOCIAL})
    assert all(s.tier is not SourceTier.SOCIAL for s in ranked)
    assert any(s.tier is SourceTier.GITHUB for s in ranked)
