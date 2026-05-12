import json
import logging
import re

from competiq.graph.state import ResearchPlan
from competiq.llm.router import router

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are the lead analyst on a competitive intelligence team.
Given a SaaS company name, design a research plan: 3-4 specific search queries for each of three dimensions.

Output STRICTLY as JSON in this format (no prose, no markdown fences):
{
  "market_queries": ["...", "...", "..."],
  "signal_queries": ["...", "...", "..."],
  "news_queries": ["...", "...", "..."]
}

- market_queries: pricing, competitors, alternatives, market positioning
- signal_queries: developer/community sentiment (reddit, hacker news, github, dev twitter)
- news_queries: recent product launches, funding, executive hires (last 6 months)

Each query should be specific and likely to surface useful results. Output JSON only."""


def _default_plan(company: str) -> ResearchPlan:
    return ResearchPlan(
        market_queries=[
            f"{company} pricing tiers",
            f"{company} alternatives competitors",
            f"{company} review comparison g2",
        ],
        signal_queries=[
            f"{company} reddit discussion",
            f"{company} hacker news thread",
            f"{company} github stars community",
        ],
        news_queries=[
            f"{company} news 2026",
            f"{company} funding round announcement",
            f"{company} product launch beta",
        ],
    )


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in planner output")
    return json.loads(match.group())


async def plan_research(company: str) -> ResearchPlan:
    response = await router.complete(
        prompt=f"Company: {company}",
        system=SYSTEM_PROMPT,
        max_tokens=600,
    )
    try:
        data = _extract_json(response.text)
        plan = ResearchPlan(**data)
        logger.info(
            "Planner OK: %d market / %d signal / %d news queries (via %s)",
            len(plan.market_queries),
            len(plan.signal_queries),
            len(plan.news_queries),
            response.provider,
        )
        return plan
    except Exception as e:
        logger.warning("Planner JSON parse failed (%s); using default queries", e)
        return _default_plan(company)
