"""Searcher agent — runs the planner's queries against configured search engines.

Concurrent across queries; each engine call is retry+timeout wrapped inside web_search_async."""

from __future__ import annotations

import asyncio
import logging

from researchhq.config import settings
from researchhq.search.web_search import SearchResult, web_search_async

logger = logging.getLogger(__name__)


async def search_all(
    queries: list[str],
    *,
    results_per_query: int | None = None,
) -> list[SearchResult]:
    n_per = results_per_query if results_per_query is not None else settings.max_results_per_query

    async def _run(q: str) -> list[SearchResult]:
        try:
            return await web_search_async(
                q,
                n_per,
                settings.search_engines,
            )
        except Exception as e:  # noqa: BLE001 — partial failure tolerated
            logger.warning("Searcher: query '%s' failed: %s", q, e)
            return []

    batches = await asyncio.gather(*[_run(q) for q in queries], return_exceptions=False)
    seen: set[str] = set()
    out: list[SearchResult] = []
    for batch in batches:
        for r in batch:
            if r.url and r.url not in seen:
                seen.add(r.url)
                out.append(r)
    logger.info("Searcher collected %d unique results across %d queries", len(out), len(queries))
    return out
