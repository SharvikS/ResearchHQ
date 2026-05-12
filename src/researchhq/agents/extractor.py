"""Fact extractor — pulls atomic claims from ranked sources via the LLM.

Inputs:
- Ranked sources (URL/title/snippet) — always available.
- Fetched page text for top-N — when present, the LLM is grounded in real content.

Post-LLM, every fact's evidence_urls is hard-validated against the known-source set
by `citation_guard.validate_evidence_urls`. URLs not in the set are dropped, and
high-confidence claims that lose all evidence are demoted.
"""

from __future__ import annotations

import json
import logging
import re

from researchhq.agents.citation_guard import CitationViolation, validate_evidence_urls
from researchhq.agents.fetcher import FetchedPage
from researchhq.llm.router import router
from researchhq.reports.schema import Fact
from researchhq.search.source_quality import RankedSource

logger = logging.getLogger(__name__)


def _system(min_facts: int) -> str:
    return f"""You are a research analyst extracting atomic factual claims from ranked sources.

Output STRICTLY as JSON:
{{
  "facts": [
    {{"claim": "...", "evidence_urls": ["..."], "confidence": 0.0}}
  ]
}}

Rules:
- One concrete claim per item. No opinions, no marketing language.
- evidence_urls MUST be a subset of the URLs provided to you. Do NOT invent URLs.
- confidence: 0.9+ when claim is directly stated by HIGH-tier sources, 0.5-0.7 for blogs/community, 0.3- for inferred.
- Skip claims you cannot ground in the provided sources.
- Aim to surface at least {min_facts} distinct atomic claims if the sources support that many; do not pad with low-value or duplicate claims.
- Output JSON only - no prose, no fences."""


def _format_sources(sources: list[RankedSource]) -> str:
    lines = []
    for i, s in enumerate(sources, 1):
        lines.append(
            f"[{i}] tier={s.tier.value} score={s.score} {s.title}\n"
            f"    URL: {s.url}\n"
            f"    {s.snippet}"
        )
    return "\n\n".join(lines) if lines else "(no sources)"


def _format_pages(pages: list[FetchedPage]) -> str:
    if not pages:
        return "(no fetched content; rely on snippets above)"
    parts = []
    for p in pages:
        if not p.text:
            continue
        parts.append(f"--- URL: {p.url} ---\n{p.text}")
    return "\n\n".join(parts) if parts else "(fetched but empty)"


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object in extractor output")
    return json.loads(match.group())


async def extract(
    query: str,
    sources: list[RankedSource],
    pages: list[FetchedPage] | None = None,
    *,
    max_tokens: int = 1400,
    min_facts: int = 12,
) -> tuple[list[Fact], list[CitationViolation]]:
    """Returns (facts, violations). Never raises on LLM failure — returns empty facts instead."""
    if not sources:
        return [], []

    pages = pages or []
    prompt = (
        f"User research query: {query}\n\n"
        f"Ranked sources:\n{_format_sources(sources)}\n\n"
        f"Fetched page content (authoritative — prefer this over snippets):\n{_format_pages(pages)}"
    )

    try:
        response = await router.complete(
            prompt=prompt, system=_system(min_facts), max_tokens=max_tokens, stage="extractor"
        )
        data = _extract_json(response.text)
    except Exception as e:  # noqa: BLE001
        logger.warning("Extractor failed (%s); returning empty fact set.", e)
        return [], []

    raw_facts: list[Fact] = []
    for item in data.get("facts", []):
        try:
            claim = str(item.get("claim", "")).strip()
            urls = [u for u in item.get("evidence_urls", []) if isinstance(u, str)]
            conf = float(item.get("confidence", 0.5))
            if claim:
                raw_facts.append(Fact(claim=claim, evidence_urls=urls, confidence=conf))
        except Exception:  # noqa: BLE001
            continue

    cleaned, violations = validate_evidence_urls(raw_facts, [s.url for s in sources])
    if violations:
        logger.info("Extractor: %d citation violations recorded", len(violations))
    return cleaned, violations
