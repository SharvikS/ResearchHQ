from competiq.graph.state import AgentFinding
from competiq.llm.router import router


SYSTEM_PROMPT = """You are a senior competitive intelligence analyst writing for a SaaS founder or CPO.
You will receive sub-reports from three specialist agents: MARKET, SIGNALS, NEWS.

Synthesize a unified intelligence briefing using these sections (markdown headings):

1. **Snapshot** — 2 sentences on the company's current position
2. **Competitive landscape** — competitors and how they differentiate
3. **Momentum** — what's happening in the last 6 months
4. **Community pulse** — what users and developers actually say
5. **Strategic gaps & opportunities** — 2 to 3 sharp observations a founder could act on
6. **Confidence note** — what's well-supported vs. weak in this analysis

Be terse, specific, citation-aware. Aim for ~400 words.
Do not introduce new claims beyond what the sub-reports support."""


async def synthesize(company: str, findings: list[AgentFinding]) -> tuple[str, str]:
    sections = []
    for f in findings:
        sections.append(f"## {f.agent.upper()} sub-report\n\n{f.summary}\n")
    body = "\n".join(sections)

    prompt = f"Company: {company}\n\nSub-reports from worker agents:\n\n{body}"

    response = await router.complete(
        prompt=prompt,
        system=SYSTEM_PROMPT,
        max_tokens=1200,
        prefer="gemini",  # Gemini Flash gives better synthesis if configured; otherwise falls back to Groq
    )
    return response.text, response.provider
