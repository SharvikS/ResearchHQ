"""Source classification and quality ranking for any research mode.

Tier order (highest first):
    OFFICIAL       — vendor/company-owned site or product docs
    ACADEMIC       — peer-reviewed, preprint servers, .edu
    GOVERNMENT     — .gov, .mil, intergovernmental bodies
    NEWS           — established news/trade press
    DOCS           — technical documentation (non-owned)
    GITHUB         — code repositories
    COMPARISON     — review aggregators (G2, Capterra, etc.)
    WIKI           — Wikipedia, etc.
    COMMUNITY      — Reddit, HN, StackExchange, dev.to
    SOCIAL         — Twitter/X, LinkedIn, YouTube, TikTok
    BLOG           — generic blog posts not on an authoritative domain
    LOW_QUALITY    — content farms, link aggregators
    SEARCH_ENGINE  — search aggregator pages (filtered out)
    OTHER          — uncategorized
"""

from __future__ import annotations

from enum import Enum
from urllib.parse import urlparse

from pydantic import BaseModel


class SourceTier(str, Enum):
    OFFICIAL = "official"
    ACADEMIC = "academic"
    GOVERNMENT = "government"
    NEWS = "news"
    DOCS = "docs"
    GITHUB = "github"
    COMPARISON = "comparison"
    WIKI = "wiki"
    COMMUNITY = "community"
    SOCIAL = "social"
    BLOG = "blog"
    LOW_QUALITY = "low_quality"
    SEARCH_ENGINE = "search_engine"
    OTHER = "other"


# Default credibility per tier (1-10). Mode-specific weighting can shift these.
TIER_BASE_SCORE: dict[SourceTier, int] = {
    SourceTier.OFFICIAL: 10,
    SourceTier.ACADEMIC: 10,
    SourceTier.GOVERNMENT: 10,
    SourceTier.NEWS: 8,
    SourceTier.DOCS: 8,
    SourceTier.GITHUB: 7,
    SourceTier.COMPARISON: 7,
    SourceTier.WIKI: 6,
    SourceTier.COMMUNITY: 5,
    SourceTier.SOCIAL: 4,
    SourceTier.BLOG: 4,
    SourceTier.LOW_QUALITY: 1,
    SourceTier.SEARCH_ENGINE: 0,
    SourceTier.OTHER: 3,
}


class RankedSource(BaseModel):
    url: str
    title: str
    snippet: str
    tier: SourceTier
    score: int
    domain: str = ""


# Domain registries
NEWS_DOMAINS = {
    "techcrunch.com", "theverge.com", "venturebeat.com", "bloomberg.com",
    "reuters.com", "wsj.com", "forbes.com", "businesswire.com", "prnewswire.com",
    "axios.com", "cnbc.com", "ft.com", "businessinsider.com", "fortune.com",
    "fastcompany.com", "thenextweb.com", "wired.com", "arstechnica.com",
    "engadget.com", "bbc.com", "cnn.com", "nytimes.com", "theinformation.com",
    "sifted.eu", "techradar.com", "zdnet.com", "economist.com", "guardian.com",
    "theguardian.com", "apnews.com", "npr.org", "aljazeera.com",
}

ACADEMIC_DOMAINS = {
    "arxiv.org", "ssrn.com", "biorxiv.org", "medrxiv.org",
    "papers.nips.cc", "openreview.net", "aclanthology.org",
    "semanticscholar.org", "scholar.google.com",
    "nature.com", "science.org", "cell.com", "ieee.org", "acm.org",
    "springer.com", "link.springer.com", "sciencedirect.com",
    "tandfonline.com", "wiley.com", "onlinelibrary.wiley.com",
    "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "plos.org", "mdpi.com",
}

SEARCH_AGGREGATOR_DOMAINS = {
    "google.com", "bing.com", "yandex.com", "yahoo.com", "duckduckgo.com",
    "html.duckduckgo.com", "brave.com", "search.brave.com", "mojeek.com",
    "grokipedia.com", "presearch.com", "ecosia.org", "startpage.com",
    "search.yahoo.com",
}

COMMUNITY_DOMAINS = {
    "reddit.com", "old.reddit.com", "news.ycombinator.com", "lobste.rs",
    "stackoverflow.com", "stackexchange.com", "quora.com", "indiehackers.com",
    "dev.to", "hashnode.com", "medium.com",
}

SOCIAL_DOMAINS = {
    "twitter.com", "x.com", "linkedin.com", "mastodon.social", "bsky.app",
    "facebook.com", "instagram.com", "youtube.com", "tiktok.com", "threads.net",
}

COMPARISON_DOMAINS = {
    "g2.com", "capterra.com", "gartner.com", "trustradius.com",
    "alternativeto.net", "producthunt.com", "saasworthy.com", "softwareadvice.com",
    "getapp.com", "slashdot.org", "pcmag.com",
}

WIKI_DOMAINS = {"wikipedia.org", "en.wikipedia.org", "wikidata.org", "fandom.com"}

GITHUB_DOMAINS = {"github.com", "gist.github.com", "gitlab.com", "bitbucket.org", "huggingface.co"}

LOW_QUALITY_HINTS = {
    "ezinearticles.com", "buzzfeed.com", "answers.com", "wikihow.com",
}


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _slug(name: str) -> str:
    return "".join(c.lower() for c in name if c.isalnum())


def _domain_in(domain: str, registry: set[str]) -> bool:
    if domain in registry:
        return True
    return any(domain.endswith("." + d) for d in registry)


def classify(url: str, subject: str = "") -> SourceTier:
    """Classify a URL into a SourceTier. `subject` is the topic/company name (optional)."""
    domain = _domain(url)
    path = urlparse(url).path.lower() if url else ""

    if not domain:
        return SourceTier.OTHER

    if _domain_in(domain, SEARCH_AGGREGATOR_DOMAINS) or "/search" in path:
        return SourceTier.SEARCH_ENGINE

    # Government / institutional first (.gov, .mil, .int, .edu)
    if domain.endswith(".gov") or ".gov." in domain or domain.endswith(".mil") or domain.endswith(".int"):
        return SourceTier.GOVERNMENT
    if domain.endswith(".edu") or ".edu." in domain:
        return SourceTier.ACADEMIC

    if _domain_in(domain, ACADEMIC_DOMAINS):
        return SourceTier.ACADEMIC
    if _domain_in(domain, NEWS_DOMAINS):
        return SourceTier.NEWS
    if _domain_in(domain, COMPARISON_DOMAINS):
        return SourceTier.COMPARISON
    if _domain_in(domain, WIKI_DOMAINS):
        return SourceTier.WIKI
    if _domain_in(domain, GITHUB_DOMAINS):
        return SourceTier.GITHUB
    if _domain_in(domain, COMMUNITY_DOMAINS):
        return SourceTier.COMMUNITY
    if _domain_in(domain, SOCIAL_DOMAINS):
        return SourceTier.SOCIAL
    if _domain_in(domain, LOW_QUALITY_HINTS):
        return SourceTier.LOW_QUALITY

    # Subject-owned domain
    slug = _slug(subject) if subject else ""
    if slug and (slug in domain.replace(".", "") or domain.startswith(slug)):
        if domain.startswith("docs.") or "/docs" in path or "developer" in domain:
            return SourceTier.DOCS
        return SourceTier.OFFICIAL

    if domain.startswith("docs.") or "/docs/" in path or domain.startswith("developer."):
        return SourceTier.DOCS
    if domain.startswith("blog.") or "/blog/" in path:
        return SourceTier.BLOG

    return SourceTier.OTHER


def rank_sources(
    raw: list[tuple[str, str, str]],
    subject: str = "",
    tier_weights: dict[SourceTier, int] | None = None,
    drop_tiers: set[SourceTier] | None = None,
) -> list[RankedSource]:
    """Classify and rank. `raw` is a list of (url, title, snippet)."""
    drop_tiers = drop_tiers or {SourceTier.SEARCH_ENGINE}
    weights = dict(TIER_BASE_SCORE)
    if tier_weights:
        weights.update(tier_weights)

    out: list[RankedSource] = []
    seen: set[str] = set()
    for url, title, snippet in raw:
        if not url or url in seen:
            continue
        seen.add(url)
        tier = classify(url, subject)
        if tier in drop_tiers:
            continue
        out.append(
            RankedSource(
                url=url,
                title=title,
                snippet=snippet,
                tier=tier,
                score=weights.get(tier, 3),
                domain=_domain(url),
            )
        )
    out.sort(key=lambda s: s.score, reverse=True)
    return out


def group_by_tier(sources: list[RankedSource]) -> dict[SourceTier, list[RankedSource]]:
    grouped: dict[SourceTier, list[RankedSource]] = {}
    for s in sources:
        grouped.setdefault(s.tier, []).append(s)
    return grouped
