import logging
from dataclasses import dataclass

from ddgs import DDGS

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def web_search(query: str, max_results: int = 8) -> list[SearchResult]:
    """Free web search via DuckDuckGo. No API key required."""
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
            )
            for r in results
        ]
    except Exception as e:
        logger.error("Search failed for query '%s': %s", query, e)
        return []


def format_results(results: list[SearchResult]) -> str:
    if not results:
        return "(no results)"
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.title}\n    {r.url}\n    {r.snippet}")
    return "\n\n".join(lines)
