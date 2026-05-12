"""Verifier — deterministic, mode-aware rule engine.

Replaces the previous narrative-only verifier. Each rule is a small function returning
`(passed, severity, message)`. Confidence is derived mechanically from rule outcomes;
violation lists are surfaced into the final report so users see what was caught.

Severity levels:
- 'fail': hard failure that materially reduces confidence (e.g. invented URL)
- 'warn': soft failure that lowers confidence but doesn't invalidate
- 'info': observational; no confidence impact
"""

from __future__ import annotations

import re
from typing import Callable

from researchhq.agents.citation_guard import CitationViolation
from researchhq.modes.base import ResearchMode
from researchhq.reports.schema import Fact, RuleResult, Section, VerifierNote
from researchhq.search.source_quality import RankedSource, SourceTier

# Tiers considered authoritative for confidence math.
HIGH_TIERS = {
    SourceTier.OFFICIAL,
    SourceTier.ACADEMIC,
    SourceTier.GOVERNMENT,
    SourceTier.NEWS,
    SourceTier.DOCS,
}

CONF_PENALTIES = {"fail": 0.10, "warn": 0.05, "info": 0.0}

# --- helpers -----------------------------------------------------------------

_NUMERIC = re.compile(r"\$?\d|\b\d+(?:\.\d+)?(?:\s?(?:%|bn|billion|m|million|k|thousand))\b", re.IGNORECASE)
_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_ATTRIBUTION_HINT = re.compile(
    r"\b(according to|reports?|stated|said|by\s+[A-Z][a-zA-Z]+|gartner|idc|forrester|statista|mckinsey|bloomberg|reuters|tech\w+|press release)\b",
    re.IGNORECASE,
)
_PAPER_REF = re.compile(
    r"\b(et al\.?|arxiv|doi|preprint|paper|study|published in|conference|proceedings|journal)\b",
    re.IGNORECASE,
)


def _domain_of(url: str) -> str:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _evidence_tiers(fact: Fact, sources: list[RankedSource]) -> list[SourceTier]:
    by_url = {s.url: s.tier for s in sources}
    return [by_url[u] for u in fact.evidence_urls if u in by_url]


def _evidence_domains(fact: Fact, sources: list[RankedSource]) -> set[str]:
    by_url = {s.url: s.domain or _domain_of(s.url) for s in sources}
    return {by_url[u] for u in fact.evidence_urls if u in by_url}


# --- shared rules ------------------------------------------------------------


def rule_no_citation_violations(
    violations: list[CitationViolation], **_: object
) -> RuleResult:
    n = len(violations)
    return RuleResult(
        name="citations.all_known_urls",
        severity="fail" if n else "info",
        passed=n == 0,
        message=("No invented URLs in citations." if n == 0
                 else f"{n} citation violation(s) — invented or unknown URLs detected and stripped/recorded."),
    )


def rule_high_conf_needs_high_tier(
    facts: list[Fact], sources: list[RankedSource], **_: object
) -> RuleResult:
    bad: list[str] = []
    for f in facts:
        if f.confidence >= 0.8:
            tiers = _evidence_tiers(f, sources)
            if not any(t in HIGH_TIERS for t in tiers):
                bad.append(f.claim[:60])
    return RuleResult(
        name="claims.high_conf_high_tier",
        severity="fail" if bad else "info",
        passed=not bad,
        message=("All high-confidence claims have at least one high-tier source." if not bad
                 else f"{len(bad)} high-confidence claim(s) lack a high-tier source: " + "; ".join(bad)),
    )


def rule_source_diversity(sources: list[RankedSource], **_: object) -> RuleResult:
    domains = {(s.domain or _domain_of(s.url)) for s in sources}
    domains.discard("")
    return RuleResult(
        name="sources.domain_diversity",
        severity="warn" if len(domains) < 3 else "info",
        passed=len(domains) >= 3,
        message=f"{len(domains)} distinct domain(s) across {len(sources)} sources.",
    )


def rule_minimum_sources(sources: list[RankedSource], **_: object) -> RuleResult:
    return RuleResult(
        name="sources.minimum_count",
        severity="fail" if len(sources) < 3 else "info",
        passed=len(sources) >= 3,
        message=f"{len(sources)} ranked source(s) retained.",
    )


# --- mode-specific rules -----------------------------------------------------


def rule_news_multi_source(
    facts: list[Fact], sources: list[RankedSource], **_: object
) -> RuleResult:
    """Each high-confidence fact in news mode must have >=2 NEWS sources from distinct domains."""
    by_url = {s.url: s for s in sources}
    failures: list[str] = []
    for f in facts:
        if f.confidence < 0.7:
            continue
        news_domains = {
            (by_url[u].domain or _domain_of(by_url[u].url))
            for u in f.evidence_urls
            if u in by_url and by_url[u].tier is SourceTier.NEWS
        }
        news_domains.discard("")
        if len(news_domains) < 2:
            failures.append(f.claim[:60])
    return RuleResult(
        name="news.multi_source_corroboration",
        severity="fail" if failures else "info",
        passed=not failures,
        message=("All key claims corroborated by >=2 NEWS domains." if not failures
                 else f"{len(failures)} single-source news claim(s) flagged unconfirmed: " + "; ".join(failures)),
    )


def rule_market_dated_attribution(
    facts: list[Fact], sections: list[Section], **_: object
) -> RuleResult:
    """Numeric figures (% / $ / billions / millions) must show a year OR an attribution phrase."""
    failures: list[str] = []
    candidates = [f.claim for f in facts] + [s.body for s in sections]
    for text in candidates:
        if not _NUMERIC.search(text):
            continue
        if _YEAR.search(text) or _ATTRIBUTION_HINT.search(text):
            continue
        failures.append(text[:80])
    return RuleResult(
        name="market.dated_attributable_figures",
        severity="fail" if failures else "info",
        passed=not failures,
        message=("All market figures carry a date or attribution." if not failures
                 else f"{len(failures)} numeric figure(s) lack date/attribution: " + " | ".join(failures[:3])),
    )


def rule_academic_paper_attribution(
    facts: list[Fact], sources: list[RankedSource], **_: object
) -> RuleResult:
    """High-confidence facts in academic mode must reference an ACADEMIC source AND
    the claim text should look like it points to a paper (et al., arxiv, study, etc.)."""
    failures: list[str] = []
    for f in facts:
        if f.confidence < 0.7:
            continue
        tiers = _evidence_tiers(f, sources)
        has_academic = any(t is SourceTier.ACADEMIC for t in tiers)
        looks_like_paper_ref = bool(_PAPER_REF.search(f.claim))
        if not (has_academic and looks_like_paper_ref):
            failures.append(f.claim[:60])
    return RuleResult(
        name="academic.paper_level_attribution",
        severity="fail" if failures else "info",
        passed=not failures,
        message=("All key claims trace to an academic paper reference." if not failures
                 else f"{len(failures)} claim(s) lack academic source or paper reference: " + "; ".join(failures)),
    )


# --- engine ------------------------------------------------------------------

Rule = Callable[..., RuleResult]

SHARED_RULES: list[Rule] = [
    rule_minimum_sources,
    rule_source_diversity,
    rule_no_citation_violations,
    rule_high_conf_needs_high_tier,
]

MODE_RULES: dict[str, list[Rule]] = {
    "news": [rule_news_multi_source],
    "market": [rule_market_dated_attribution],
    "academic": [rule_academic_paper_attribution],
}


def verify(
    mode: ResearchMode,
    sources: list[RankedSource],
    facts: list[Fact],
    *,
    sections: list[Section] | None = None,
    violations: list[CitationViolation] | None = None,
) -> VerifierNote:
    sections = sections or []
    violations = violations or []

    ctx = {
        "sources": sources,
        "facts": facts,
        "sections": sections,
        "violations": violations,
    }

    rules: list[Rule] = list(SHARED_RULES) + list(MODE_RULES.get(mode.name, []))
    results: list[RuleResult] = [r(**ctx) for r in rules]

    if not sources:
        return VerifierNote(
            overall_confidence=0.0,
            notes=["No sources collected."],
            rules=results,
            violations=violations,
        )

    # Base from share of high-tier sources.
    high = sum(1 for s in sources if s.tier in HIGH_TIERS)
    base = 0.4 + 0.5 * (high / max(1, len(sources)))  # 0.4 .. 0.9

    # Subtract penalties for failing rules.
    for r in results:
        if not r.passed:
            base -= CONF_PENALTIES[r.severity]

    # Pull toward avg fact confidence to reward grounded extraction.
    if facts:
        avg = sum(f.confidence for f in facts) / len(facts)
        base = (base + avg) / 2

    base = max(0.0, min(1.0, base))

    notes = [r.message for r in results if not r.passed]
    notes.extend(mode.config.confidence_rules)
    return VerifierNote(
        overall_confidence=round(base, 2),
        notes=notes,
        rules=results,
        violations=violations,
    )
