"""Web search abstraction. Engines are pluggable; default is DuckDuckGo (no key).

Each engine call is wrapped with a retry+timeout loop so a single flake or hung TCP
connection never blocks the pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from researchhq.utils.retry import with_retry

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 12.0
DEFAULT_ATTEMPTS = 2


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def _ddg_search_sync(query: str, max_results: int) -> list[SearchResult]:
    try:
        from ddgs import DDGS
    except ImportError:
        logger.error("ddgs package not installed")
        return []
    with DDGS() as ddgs:
        raw = ddgs.text(query, max_results=max_results)
    return [
        SearchResult(
            title=r.get("title", ""),
            url=r.get("href", ""),
            snippet=r.get("body", ""),
        )
        for r in raw
    ]


async def _ddg_search_async(query: str, max_results: int) -> list[SearchResult]:
    return await asyncio.to_thread(_ddg_search_sync, query, max_results)


_ENGINES_ASYNC = {
    "duckduckgo": _ddg_search_async,
    "ddg": _ddg_search_async,
}


async def web_search_async(
    query: str,
    max_results: int = 6,
    engines: list[str] | None = None,
) -> list[SearchResult]:
    """Async, retry+timeout wrapped, partial-failure tolerant search."""
    engines = engines or ["duckduckgo"]
    seen: set[str] = set()
    out: list[SearchResult] = []
    for eng in engines:
        fn = _ENGINES_ASYNC.get(eng.lower())
        if fn is None:
            logger.debug("Unknown search engine: %s", eng)
            continue
        try:
            batch = await with_retry(
                lambda fn=fn: fn(query, max_results),
                attempts=DEFAULT_ATTEMPTS,
                timeout=DEFAULT_TIMEOUT_S,
                label=f"search[{eng}]:{query[:40]}",
            )
        except Exception as e:  # noqa: BLE001 — partial failure is fine
            logger.warning("Search engine %s failed for '%s' after retries: %s", eng, query, e)
            continue
        for r in batch:
            if r.url and r.url not in seen:
                seen.add(r.url)
                out.append(r)
    return out


def web_search(
    query: str,
    max_results: int = 6,
    engines: list[str] | None = None,
) -> list[SearchResult]:
    """Synchronous adapter for callers (e.g., legacy code paths or tests)."""
    return asyncio.run(web_search_async(query, max_results, engines))


def format_results(results: list[SearchResult]) -> str:
    if not results:
        return "(no results)"
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.title}\n    {r.url}\n    {r.snippet}")
    return "\n\n".join(lines)
