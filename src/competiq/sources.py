"""Classify URLs by source type and credibility for citation quality control."""

from __future__ import annotations

from enum import Enum
from urllib.parse import urlparse

from pydantic import BaseModel


class SourceType(str, Enum):
    OFFICIAL = "official"
    DOCS = "docs"
    BLOG = "blog"
    NEWS = "news"
    CRUNCHBASE = "crunchbase"
    COMPARISON = "comparison"
    WIKI = "wiki"
    GITHUB = "github"
    FORUM = "forum"
    SOCIAL = "social"
    SEARCH_AGGREGATOR = "search_aggregator"
    OTHER = "other"


class Credibility(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ClassifiedSource(BaseModel):
    url: str
    title: str
    snippet: str
    source_type: SourceType
    credibility: Credibility


NEWS_DOMAINS = {
    "techcrunch.com", "theverge.com", "venturebeat.com", "bloomberg.com",
    "reuters.com", "wsj.com", "forbes.com", "businesswire.com", "prnewswire.com",
    "axios.com", "cnbc.com", "ft.com", "businessinsider.com", "fortune.com",
    "fastcompany.com", "thenextweb.com", "wired.com", "arstechnica.com",
    "engadget.com", "bbc.com", "cnn.com", "nytimes.com", "theinformation.com",
    "sifted.eu", "techradar.com", "zdnet.com",
}

SEARCH_AGGREGATOR_DOMAINS = {
    "google.com", "bing.com", "yandex.com", "yahoo.com", "duckduckgo.com",
    "html.duckduckgo.com", "brave.com", "search.brave.com", "mojeek.com",
    "grokipedia.com", "presearch.com", "ecosia.org", "startpage.com",
    "search.yahoo.com",
}

FORUM_DOMAINS = {
    "reddit.com", "old.reddit.com", "news.ycombinator.com", "lobste.rs",
    "stackoverflow.com", "stackexchange.com", "quora.com", "indiehackers.com",
    "dev.to",
}

SOCIAL_DOMAINS = {
    "twitter.com", "x.com", "linkedin.com", "mastodon.social", "bsky.app",
    "facebook.com", "instagram.com", "youtube.com", "tiktok.com",
}

COMPARISON_DOMAINS = {
    "g2.com", "capterra.com", "gartner.com", "trustradius.com",
    "alternativeto.net", "producthunt.com", "saasworthy.com", "softwareadvice.com",
    "getapp.com", "slashdot.org",
}

CRUNCHBASE_DOMAINS = {"crunchbase.com", "tracxn.com", "pitchbook.com", "owler.com"}

WIKI_DOMAINS = {"wikipedia.org", "en.wikipedia.org", "wikidata.org"}

GITHUB_DOMAINS = {"github.com", "gist.github.com"}


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _company_slug(name: str) -> str:
    return "".join(c.lower() for c in name if c.isalnum())


def classify(url: str, company: str) -> tuple[SourceType, Credibility]:
    domain = _domain(url)
    path = urlparse(url).path.lower() if url else ""

    if not domain:
        return SourceType.OTHER, Credibility.LOW

    if domain in SEARCH_AGGREGATOR_DOMAINS or "/search" in path or "/search?" in url:
        return SourceType.SEARCH_AGGREGATOR, Credibility.LOW

    if domain in NEWS_DOMAINS or any(domain.endswith("." + d) for d in NEWS_DOMAINS):
        return SourceType.NEWS, Credibility.HIGH

    if domain in CRUNCHBASE_DOMAINS:
        return SourceType.CRUNCHBASE, Credibility.HIGH

    if domain in COMPARISON_DOMAINS:
        return SourceType.COMPARISON, Credibility.HIGH

    if domain in WIKI_DOMAINS or domain.endswith(".wikipedia.org"):
        return SourceType.WIKI, Credibility.MEDIUM

    if domain in GITHUB_DOMAINS:
        return SourceType.GITHUB, Credibility.MEDIUM

    if domain in FORUM_DOMAINS or any(domain.endswith("." + d) for d in FORUM_DOMAINS):
        return SourceType.FORUM, Credibility.MEDIUM

    if domain in SOCIAL_DOMAINS:
        return SourceType.SOCIAL, Credibility.MEDIUM

    # Company-owned domain detection
    slug = _company_slug(company)
    if slug and (slug in domain.replace(".", "") or domain.startswith(slug)):
        if domain.startswith("docs.") or "/docs" in path or "developer" in domain:
            return SourceType.DOCS, Credibility.HIGH
        if domain.startswith("blog.") or "/blog" in path or "/changelog" in path or "/news" in path:
            return SourceType.BLOG, Credibility.HIGH
        return SourceType.OFFICIAL, Credibility.HIGH

    # Generic patterns for non-owned but informative pages
    if domain.startswith("docs.") or "/docs/" in path or "developer" in domain:
        return SourceType.DOCS, Credibility.HIGH
    if domain.startswith("blog.") or "/blog/" in path:
        return SourceType.BLOG, Credibility.MEDIUM

    return SourceType.OTHER, Credibility.LOW


def credibility_rank(c: Credibility) -> int:
    return {Credibility.HIGH: 3, Credibility.MEDIUM: 2, Credibility.LOW: 1}[c]


def filter_and_rank(sources: list[ClassifiedSource]) -> list[ClassifiedSource]:
    """Drop search aggregators; sort remaining by credibility (high first)."""
    kept = [s for s in sources if s.source_type is not SourceType.SEARCH_AGGREGATOR]
    return sorted(kept, key=lambda s: credibility_rank(s.credibility), reverse=True)


def group_by_type(sources: list[ClassifiedSource]) -> dict[SourceType, list[ClassifiedSource]]:
    grouped: dict[SourceType, list[ClassifiedSource]] = {}
    for s in sources:
        grouped.setdefault(s.source_type, []).append(s)
    return grouped
