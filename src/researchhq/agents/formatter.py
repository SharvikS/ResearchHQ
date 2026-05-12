"""Formatter agent — produces a 'Recommended next research questions' list and
finalizes the structured ResearchReport.

The actual rendering to markdown / json / html lives in researchhq.reports.exporter."""

from __future__ import annotations

import json
import logging
import re

from researchhq.llm.router import router
from researchhq.modes.base import ResearchMode
from researchhq.reports.schema import Section

logger = logging.getLogger(__name__)


def _system(min_q: int, max_q: int) -> str:
    return f"""You suggest follow-up research questions a careful analyst would ask next.

Output STRICTLY as JSON:
{{ "questions": ["...", "..."] }}

Rules:
- {min_q}-{max_q} questions, each specific and actionable.
- Should fill gaps that the report leaves open or open new useful angles.
- Output JSON only — no prose."""


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object")
    return json.loads(match.group())


async def next_questions(
    mode: ResearchMode,
    query: str,
    sections: list[Section],
    *,
    min_q: int = 4,
    max_q: int = 6,
) -> list[str]:
    body = "\n\n".join(f"## {s.heading}\n{s.body}" for s in sections)
    prompt = f"Mode: {mode.name}\nUser query: {query}\n\nReport so far:\n{body}"
    try:
        response = await router.complete(prompt=prompt, system=_system(min_q, max_q), max_tokens=400, stage="formatter")
        data = _extract_json(response.text)
        qs = [q for q in data.get("questions", []) if isinstance(q, str)]
        return qs[: max(max_q + 2, 8)] if qs else _fallback_questions(mode, query)
    except Exception as e:
        logger.warning("Formatter LLM failed (%s); using fallback questions.", e)
        return _fallback_questions(mode, query)


def _fallback_questions(mode: ResearchMode, query: str) -> list[str]:
    return [
        f"What primary sources would best validate the strongest claim about {query}?",
        f"What's the most recent authoritative update on {query}?",
        f"Which counter-arguments or critiques of {query} are most credible?",
        f"What adjacent {mode.name} angles haven't been explored yet?",
    ]
