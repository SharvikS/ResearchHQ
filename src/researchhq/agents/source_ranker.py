"""Source ranking agent.

Score model:
- Start from each tier's base credibility (`TIER_BASE_SCORE`).
- Apply mode-level `tier_weights` (overrides per tier).
- Apply mode-level `preferred_tiers` boost: +PREFERRED_BOOST per matching tier
  (so a NEWS source in news mode outranks a tied non-preferred source).
- `drop_tiers` is hard: such sources are excluded entirely.
"""

from __future__ import annotations

import logging

from researchhq.config import settings
from researchhq.modes.base import ResearchMode
from researchhq.search.source_quality import RankedSource, rank_sources
from researchhq.search.web_search import SearchResult

logger = logging.getLogger(__name__)

PREFERRED_BOOST = 2


def rank(
    raw: list[SearchResult],
    mode: ResearchMode,
    subject: str,
    *,
    cap: int | None = None,
) -> list[RankedSource]:
    triples = [(r.url, r.title, r.snippet) for r in raw]
    ranked = rank_sources(
        triples,
        subject=subject,
        tier_weights=mode.config.tier_weights,
        drop_tiers=mode.config.drop_tiers,
    )

    # Apply explicit preferred_tiers boost so the mode declarations are not decorative.
    preferred = set(mode.config.preferred_tiers or [])
    if preferred:
        boosted: list[RankedSource] = []
        for s in ranked:
            score = s.score + (PREFERRED_BOOST if s.tier in preferred else 0)
            boosted.append(s.model_copy(update={"score": score}))
        boosted.sort(key=lambda s: s.score, reverse=True)
        ranked = boosted

    limit = cap if cap is not None else settings.max_total_sources
    capped = ranked[:limit]
    logger.info(
        "Source ranker kept %d/%d sources (top tier: %s)",
        len(capped),
        len(raw),
        capped[0].tier.value if capped else "n/a",
    )
    return capped
