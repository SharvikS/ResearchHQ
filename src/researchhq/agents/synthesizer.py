"""Synthesizer — composes the report sections defined by the active mode.

Inputs:
- Mode-derived section skeleton.
- Ranked sources + fetched page content (grounded synthesis).
- Validated facts.

Post-LLM, every section body is run through `strip_unknown_citations` so any
inline link to a URL not in the known source set is stripped (text retained, URL removed).
"""

from __future__ import annotations

import logging

from researchhq.agents.citation_guard import CitationViolation, strip_unknown_citations
from researchhq.agents.fetcher import FetchedPage
from researchhq.llm.router import router
from researchhq.modes.base import ResearchMode
from researchhq.reports.schema import Fact, Section
from researchhq.search.source_quality import RankedSource

logger = logging.getLogger(__name__)


def _format_sources(sources: list[RankedSource]) -> str:
    if not sources:
        return "(no sources)"
    return "\n".join(
        f"- [{i}] ({s.tier.value}) {s.title} -- {s.url}\n  {s.snippet}"
        for i, s in enumerate(sources, 1)
    )


def _format_pages(pages: list[FetchedPage], budget_chars: int | None = None) -> str:
    """Render fetched-page content, capped at `budget_chars` total.

    Pages are consumed in input order (synthesizer receives them rank-sorted).
    The last page included may be truncated to honor the budget. This
    decouples synthesis cost from how aggressively the fetcher pulled.
    """
    parts: list[str] = []
    used = 0
    for p in pages:
        if not p.text:
            continue
        header = f"--- URL: {p.url} ---\n"
        if budget_chars is None:
            parts.append(header + p.text)
            continue
        remaining = budget_chars - used
        if remaining <= len(header) + 50:
            break
        body_room = remaining - len(header)
        body = p.text if len(p.text) <= body_room else p.text[:body_room] + " [...truncated]"
        parts.append(header + body)
        used += len(header) + len(body)
    return "\n\n".join(parts) if parts else "(no fetched content)"


def _format_facts(facts: list[Fact]) -> str:
    if not facts:
        return "(no extracted facts)"
    return "\n".join(
        f"- {f.claim}  [conf {f.confidence:.2f}]  evidence: {', '.join(f.evidence_urls) or 'n/a'}"
        for f in facts
    )


def _section_brief(mode: ResearchMode) -> str:
    excluded = {"Sources", "Confidence score", "Recommended next research questions"}
    return "\n".join(
        f"- {s.heading}{'' if s.required else ' (optional, omit if no evidence)'}"
        for s in mode.report_skeleton()
        if s.heading not in excluded
    )


def _system(mode: ResearchMode, depth_directive: str) -> str:
    persona = mode.config.synthesizer_persona or "You are a senior research analyst."
    rules = "\n".join(f"- {r}" for r in mode.config.confidence_rules) or "- Be honest about gaps."
    return f"""{persona}

Compose a report using these sections (markdown headings, in order):
{_section_brief(mode)}

Rules:
- Cite inline using markdown link syntax: [claim text](URL).
- Use ONLY URLs from the sources block below. Do NOT invent URLs.
- Prefer high-tier sources. Mark unsupported claims as 'insufficient data'.
- Be specific and citation-aware. Do not invent quantities, dates, or names.
- {depth_directive}

Confidence rules for this mode:
{rules}

Output ONLY the markdown for the requested sections. Do not output the source list, confidence
score, or next-questions sections - those are added programmatically."""


async def synthesize(
    mode: ResearchMode,
    query: str,
    sources: list[RankedSource],
    facts: list[Fact],
    pages: list[FetchedPage] | None = None,
    *,
    max_tokens: int = 1800,
    depth_directive: str = (
        "Be specific and citation-aware. Mix bullets for findings with short "
        "paragraphs for context. Cite high-tier sources inline."
    ),
    page_budget_chars: int | None = None,
) -> tuple[list[Section], str, list[CitationViolation]]:
    """Returns (sections, provider, violations).

    Never raises on LLM failure: returns a single stub section noting the
    failure (matching the extractor's behavior) so the pipeline can complete
    and the user still gets sources, facts, and follow-up questions.
    """
    pages = pages or []
    user = (
        f"User research query: {query}\n\n"
        f"Extracted facts:\n{_format_facts(facts)}\n\n"
        f"Ranked sources (these URLs are the ONLY allowed citation targets):\n{_format_sources(sources)}\n\n"
        f"Fetched page content (authoritative):\n{_format_pages(pages, page_budget_chars)}"
    )
    try:
        response = await router.complete(
            prompt=user, system=_system(mode, depth_directive), max_tokens=max_tokens, stage="synthesizer"
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Synthesizer LLM failed (%s); returning stub section.", e)
        stub = Section(
            heading="Findings",
            body=(
                "_Synthesis stage could not produce a report — all configured "
                f"LLM providers failed (last error: `{type(e).__name__}: {e}`). "
                "Sources, extracted facts, and follow-up questions below are "
                "still available._"
            ),
        )
        return [stub], "none", []

    raw_sections = _split_markdown_sections(response.text, mode)

    known_urls = [s.url for s in sources]
    cleaned_sections: list[Section] = []
    violations: list[CitationViolation] = []
    for sec in raw_sections:
        clean_body, sec_violations = strip_unknown_citations(
            sec.body, known_urls, location=sec.heading
        )
        cleaned_sections.append(Section(heading=sec.heading, body=clean_body))
        violations.extend(sec_violations)
    if violations:
        logger.info("Synthesizer: stripped %d unknown citations", len(violations))
    return cleaned_sections, response.provider, violations


def _split_markdown_sections(md: str, mode: ResearchMode) -> list[Section]:
    skeleton = [
        s.heading for s in mode.report_skeleton()
        if s.heading not in {"Sources", "Confidence score", "Recommended next research questions"}
    ]
    out: list[Section] = []
    current_heading: str | None = None
    buf: list[str] = []

    def _flush() -> None:
        if current_heading is not None:
            out.append(Section(heading=current_heading, body="\n".join(buf).strip()))

    for line in md.splitlines():
        stripped = line.lstrip("# ").strip().rstrip(":")
        is_heading = line.lstrip().startswith("#") and len(line.strip()) > 1
        match = next(
            (h for h in skeleton if h.lower() == stripped.lower()), None
        ) if is_heading else None
        if match:
            _flush()
            current_heading = match
            buf = []
        else:
            buf.append(line)
    _flush()

    if not out:
        out = [Section(heading="Findings", body=md.strip())]
    return out
