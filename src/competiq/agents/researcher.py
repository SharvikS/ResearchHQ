import logging
from dataclasses import dataclass

from competiq.llm.router import router
from competiq.tools.search import format_results, web_search

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a competitive intelligence analyst for SaaS companies.
Given web search results about a company, write a concise (~250 word) briefing covering:

1. **What the company does** — one sentence
2. **Direct competitors** — 3 to 5, with one-line differentiator each
3. **Recent moves** — only if visible in the results (product launches, funding, hires)
4. **Strategic observation** — one sharp insight a founder or PM could act on

Cite source numbers in brackets like [1], [2] when making specific claims.
Be precise. If results don't support a section, say "insufficient data" rather than guess.
Output clean markdown."""


@dataclass
class ResearchBriefing:
    company: str
    briefing: str
    sources: list[str]
    provider_used: str


async def research_company(company: str) -> ResearchBriefing:
    queries = [
        f"{company} SaaS competitors comparison",
        f"{company} latest news 2026",
        f"{company} pricing features",
    ]

    all_results = []
    for q in queries:
        all_results.extend(web_search(q, max_results=5))

    # Dedupe by URL while preserving order
    seen: set[str] = set()
    unique = []
    for r in all_results:
        if r.url and r.url not in seen:
            seen.add(r.url)
            unique.append(r)

    top = unique[:15]
    formatted = format_results(top)
    prompt = f"Company: {company}\n\nSearch results:\n{formatted}"

    response = await router.complete(prompt, system=SYSTEM_PROMPT, max_tokens=800)

    return ResearchBriefing(
        company=company,
        briefing=response.text,
        sources=[r.url for r in top],
        provider_used=response.provider,
    )
