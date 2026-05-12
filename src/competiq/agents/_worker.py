import asyncio
import time

from competiq.graph.state import AgentFinding
from competiq.llm.router import router
from competiq.sources import ClassifiedSource, classify, filter_and_rank
from competiq.tools.search import web_search


def _format_for_llm(sources: list[ClassifiedSource]) -> str:
    """Render sources as a numbered list with full URLs and credibility tags
    so the LLM can build inline markdown links."""
    if not sources:
        return "(no high-quality sources found)"
    lines = []
    for i, s in enumerate(sources, 1):
        lines.append(
            f"[{i}] ({s.credibility.value} credibility, {s.source_type.value}) {s.title}\n"
            f"    URL: {s.url}\n"
            f"    {s.snippet}"
        )
    return "\n\n".join(lines)


async def run_worker_agent(
    name: str,
    company: str,
    queries: list[str],
    system_prompt: str,
    max_results_per_query: int = 5,
    max_total_sources: int = 12,
    max_tokens: int = 700,
) -> AgentFinding:
    """Search → classify → filter → summarize. Returns finding with cited URLs."""
    started = time.perf_counter()

    raw = []
    for q in queries:
        results = await asyncio.to_thread(web_search, q, max_results_per_query)
        raw.extend(results)

    # Dedupe by URL
    seen: set[str] = set()
    deduped = []
    for r in raw:
        if r.url and r.url not in seen:
            seen.add(r.url)
            deduped.append(r)

    # Classify and filter out search-engine result pages + low-quality noise
    classified = [
        ClassifiedSource(
            url=r.url,
            title=r.title,
            snippet=r.snippet,
            **dict(zip(("source_type", "credibility"), classify(r.url, company))),
        )
        for r in deduped
    ]
    ranked = filter_and_rank(classified)[:max_total_sources]

    formatted = _format_for_llm(ranked)
    prompt = (
        f"Company: {company}\n\n"
        f"Sources (already filtered for quality, ranked high to low credibility):\n{formatted}\n\n"
        f"Task: Write your section. CITE INLINE using markdown link syntax: "
        f"[claim text](exact URL from sources above). Use only URLs that appear above. "
        f"Prefer high-credibility sources for any factual claim."
    )

    response = await router.complete(prompt=prompt, system=system_prompt, max_tokens=max_tokens)

    return AgentFinding(
        agent=name,
        summary=response.text,
        sources=ranked,
        queries=queries,
        elapsed_seconds=round(time.perf_counter() - started, 2),
        provider=response.provider,
    )
