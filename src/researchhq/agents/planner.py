"""Planner agent — turns user query + mode into a list of search queries.

LLM-augmented but degrades gracefully to mode template seeds if the LLM is unavailable
or returns malformed JSON."""

from __future__ import annotations

import json
import logging
import re

from researchhq.llm.router import router
from researchhq.modes.base import ResearchMode
from researchhq.reports.schema import ResearchPlan

logger = logging.getLogger(__name__)


def _system(min_q: int, max_q: int) -> str:
    return f"""You are a senior research planner. You will be given a user query and a research mode.
Produce a focused, deduplicated list of {min_q}-{max_q} specific web search queries that, taken together,
would let an analyst write a thorough, evidence-based report.

Output STRICTLY as JSON:
{{
  "queries": ["...", "..."],
  "rationale": "one sentence about the angle of this plan"
}}

Rules:
- Queries must be specific, not vague.
- Mix breadth and depth — at least two queries should target official/authoritative sources.
- For modes 'news' and 'academic', bias toward dated and venue-anchored queries respectively.
- Output JSON only, no prose, no fences."""


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in planner output")
    return json.loads(match.group())


def _fallback(mode: ResearchMode, query: str) -> ResearchPlan:
    return ResearchPlan(
        queries=mode.seed_queries(query),
        rationale=f"Template-based fallback plan for {mode.name} mode.",
    )


async def plan(
    mode: ResearchMode,
    query: str,
    *,
    min_queries: int = 6,
    max_queries: int = 8,
    max_tokens: int = 600,
) -> ResearchPlan:
    """Return a research plan. Never raises."""
    user_prompt = (
        f"Mode: {mode.name}\n"
        f"Mode description: {mode.config.description}\n"
        f"User query: {query}\n\n"
        f"Seed query examples (for inspiration, do not copy verbatim):\n"
        + "\n".join(f"- {q}" for q in mode.seed_queries(query))
    )
    try:
        response = await router.complete(
            prompt=user_prompt,
            system=_system(min_queries, max_queries),
            max_tokens=max_tokens,
            stage="planner",
        )
        data = _extract_json(response.text)
        queries = [q for q in data.get("queries", []) if isinstance(q, str) and q.strip()]
        if not queries:
            raise ValueError("empty queries list")
        cap = max(max_queries + 2, 10)
        return ResearchPlan(queries=queries[:cap], rationale=str(data.get("rationale", "")))
    except Exception as e:
        logger.warning("Planner LLM failed (%s); using template seeds.", e)
        return _fallback(mode, query)
