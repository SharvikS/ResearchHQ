from competiq.agents._worker import run_worker_agent
from competiq.graph.state import AgentFinding


SYSTEM_PROMPT = """You are a developer signals analyst.
Given web search results about a SaaS company, write a brief on COMMUNITY/DEVELOPER SIGNALS:

- **Sentiment** — overall vibe from HN, Reddit, dev forums (positive / mixed / critical)
- **Top complaints** — 2 to 3 specific pain points users raise
- **Adoption signals** — GitHub presence, community size, dev mentions
- **Notable mentions** — viral threads, controversies, or strong endorsements if any

Cite sources [1], [2]. ~150 words.
Say "insufficient data" if a section lacks evidence — do not invent sentiment."""


async def run_signal_agent(company: str, queries: list[str]) -> AgentFinding:
    return await run_worker_agent(
        name="signal",
        company=company,
        queries=queries,
        system_prompt=SYSTEM_PROMPT,
    )
