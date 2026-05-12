"""Deterministic citation validators.

Two operations needed:
- For extracted facts: every evidence_url must be in the known source URL set.
- For synthesized markdown: every inline link `[text](url)` must reference a known URL.
  Unknown links are stripped (text retained) so the report never displays a fabricated URL.
"""

from __future__ import annotations

import re

from researchhq.reports.schema import CitationViolation, Fact

# [text](url) — non-greedy text, URL until first whitespace or closing paren.
_MD_LINK = re.compile(r"\[([^\]]+)\]\(\s*([^)\s]+)\s*\)")

# Re-exported so callers can `from researchhq.agents.citation_guard import CitationViolation`.
__all__ = ["CitationViolation", "validate_evidence_urls", "strip_unknown_citations"]


def _normalize(url: str) -> str:
    return (url or "").strip().rstrip("/")


def validate_evidence_urls(
    facts: list[Fact],
    known_urls: list[str],
) -> tuple[list[Fact], list[CitationViolation]]:
    """Return (cleaned_facts, violations).

    For each fact:
    - Drop URLs that are not in `known_urls`.
    - If, after dropping, evidence_urls is empty AND original confidence >= 0.7, demote to 0.5
      and record a violation. (A high-confidence claim with no traceable evidence should not
      survive as 'high'.)
    - If a fact had at least one URL that survived, keep it as-is.
    - If it had no URLs at all to begin with and was high-confidence, also demote.
    """
    known = {_normalize(u) for u in known_urls if u}
    cleaned: list[Fact] = []
    violations: list[CitationViolation] = []

    for f in facts:
        kept: list[str] = []
        for u in f.evidence_urls:
            if _normalize(u) in known:
                kept.append(u)
            else:
                violations.append(
                    CitationViolation(
                        kind="extractor.unknown_url",
                        location=f.claim[:80],
                        url=u,
                        detail="evidence URL not in known source set",
                    )
                )
        new_conf = f.confidence
        if not kept and f.confidence >= 0.7:
            violations.append(
                CitationViolation(
                    kind="extractor.no_evidence",
                    location=f.claim[:80],
                    detail=f"high confidence ({f.confidence:.2f}) but no valid evidence URLs",
                )
            )
            new_conf = 0.5
        cleaned.append(
            Fact(claim=f.claim, evidence_urls=kept, confidence=new_conf)
        )
    return cleaned, violations


def strip_unknown_citations(
    markdown: str,
    known_urls: list[str],
    *,
    location: str = "",
) -> tuple[str, list[CitationViolation]]:
    """Replace `[text](unknown_url)` with `[text]` and record violations.

    Known links are left untouched. Mailto/anchor-only refs are stripped (they're not citations)."""
    known = {_normalize(u) for u in known_urls if u}
    violations: list[CitationViolation] = []

    def _sub(m: re.Match[str]) -> str:
        text, url = m.group(1), m.group(2)
        norm = _normalize(url)
        if norm in known:
            return m.group(0)
        if url.startswith(("#", "mailto:", "javascript:")):
            return f"[{text}]"
        violations.append(
            CitationViolation(
                kind="synth.unknown_url",
                location=location,
                url=url,
                detail="inline citation URL not in known source set",
            )
        )
        return f"[{text}]"

    return _MD_LINK.sub(_sub, markdown), violations
