from competiq.agents._worker import run_worker_agent
from competiq.graph.state import AgentFinding


SYSTEM_PROMPT = """You are a news analyst tracking SaaS company moves.
Given web search results, write a RECENT MOVES brief covering the last 6 months:

- **Product launches** — new features, beta releases, rebrands
- **Funding/financial** — rounds raised, valuation, M&A activity
- **People** — notable hires, departures, leadership changes

Use date format like "Mar 2026" when visible. Cite [1], [2]. ~150 words.
Say "insufficient data" for sections without evidence — do not fabricate dates or events."""


async def run_news_agent(company: str, queries: list[str]) -> AgentFinding:
    return await run_worker_agent(
        name="news",
        company=company,
        queries=queries,
        system_prompt=SYSTEM_PROMPT,
    )
