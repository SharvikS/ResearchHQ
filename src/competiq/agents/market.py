from competiq.agents._worker import run_worker_agent
from competiq.graph.state import AgentFinding


SYSTEM_PROMPT = """You are a market analyst on a competitive intelligence team.
Given filtered, classified web sources about a SaaS company, write a focused MARKET POSITION brief.

Required structure (markdown):

### Pricing model
2-3 sentences on tiers, free plan, enterprise approach. Inline-cite each fact.

### Market position
1-2 sentences on SMB / mid-market / enterprise focus. Inline-cite.

### Direct competitors comparison
A markdown table with EXACTLY these columns and 3-5 rows of named competitors:

| Competitor | Pricing | Key features | Target users | Strengths | Weaknesses |
|---|---|---|---|---|---|

Rules for the table:
- Only include competitors mentioned or strongly implied in the sources.
- For any cell where the sources don't provide direct evidence, write "unknown" — do NOT guess.
- Keep each cell under 12 words.
- Below the table, add a short paragraph contextualizing how this company differentiates from those competitors.

CITATIONS: Every factual claim in prose sections must be an inline markdown link [text](URL). Use only URLs from the provided sources. Prefer HIGH credibility sources (official, docs, news, comparison) over MEDIUM/LOW.

If the sources are too thin for a section, write "insufficient data — see Confidence note in final briefing." Do NOT fabricate."""


async def run_market_agent(company: str, queries: list[str]) -> AgentFinding:
    return await run_worker_agent(
        name="market",
        company=company,
        queries=queries,
        system_prompt=SYSTEM_PROMPT,
        max_tokens=1100,  # competitor table needs more room
    )
