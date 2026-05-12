"""Research effort levels — analogous to Claude Code's reasoning effort knob.

A single `--effort low|medium|high` flag dials every depth knob in the pipeline:
how many queries the planner generates, how many results per query, how many
sources the ranker keeps, how many pages the fetcher pulls (and how much of
each), the extractor/synthesizer token budgets, and the synthesizer's
verbosity/citation density directive.

`medium` preserves the historical default behavior so existing runs are
unchanged unless the user opts in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Effort = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class EffortProfile:
    name: Effort

    # Planner
    planner_min_queries: int
    planner_max_queries: int
    planner_max_tokens: int

    # Search + ranking
    results_per_query: int
    max_total_sources: int

    # Fetch
    fetch_top_n: int
    per_page_chars: int

    # Extract
    extractor_max_tokens: int
    extractor_min_facts: int

    # Synthesize
    synth_max_tokens: int
    synth_depth: Literal["terse", "balanced", "thorough"]
    # Total chars of fetched page content the synth prompt may include. Pages are
    # consumed in rank order until the budget is exhausted. This decouples
    # synthesis cost from how aggressively the fetcher pulled content.
    synth_page_budget_chars: int

    # Formatter
    formatter_min_q: int
    formatter_max_q: int


_SYNTH_DIRECTIVE = {
    "terse": (
        "Be terse: short bullet-style findings, 1-2 sentences each. "
        "Minimize prose. Cite once per major claim."
    ),
    "balanced": (
        "Be specific and citation-aware. Mix bullets for findings with short "
        "paragraphs for context. Cite high-tier sources inline."
    ),
    "thorough": (
        "Be comprehensive. Write multi-paragraph sections that include "
        "quantitative specifics (numbers, dates, named entities), contrasting "
        "viewpoints when sources disagree, and at least three inline "
        "citations per section. Prefer depth and analytical rigor over "
        "brevity. Surface mechanisms, second-order effects, and explicit "
        "uncertainty where the evidence is thin."
    ),
}


PROFILES: dict[str, EffortProfile] = {
    "low": EffortProfile(
        name="low",
        planner_min_queries=4, planner_max_queries=5, planner_max_tokens=400,
        results_per_query=4, max_total_sources=10,
        fetch_top_n=4, per_page_chars=2500,
        extractor_max_tokens=900, extractor_min_facts=6,
        synth_max_tokens=1200, synth_depth="terse",
        synth_page_budget_chars=10_000,
        formatter_min_q=3, formatter_max_q=4,
    ),
    "medium": EffortProfile(
        name="medium",
        planner_min_queries=6, planner_max_queries=8, planner_max_tokens=600,
        results_per_query=6, max_total_sources=18,
        fetch_top_n=8, per_page_chars=4000,
        extractor_max_tokens=1400, extractor_min_facts=12,
        synth_max_tokens=1800, synth_depth="balanced",
        synth_page_budget_chars=24_000,
        formatter_min_q=4, formatter_max_q=6,
    ),
    # `high` is tuned to fit Groq's free-tier 12_000 TPM ceiling on
    # llama-3.3-70b-versatile. Each LLM call (extractor + synthesizer) stays
    # under ~11_000 tokens (input + max_tokens) with margin.
    "high": EffortProfile(
        name="high",
        planner_min_queries=10, planner_max_queries=12, planner_max_tokens=800,
        results_per_query=8, max_total_sources=24,
        fetch_top_n=10, per_page_chars=3000,
        extractor_max_tokens=2500, extractor_min_facts=20,
        synth_max_tokens=3500, synth_depth="thorough",
        synth_page_budget_chars=20_000,
        formatter_min_q=6, formatter_max_q=10,
    ),
}


DEFAULT_EFFORT: Effort = "medium"


def get_profile(effort: str | None) -> EffortProfile:
    """Resolve an effort name (case-insensitive) to a profile.

    Falls back to the default profile if the value is None, empty, or unknown.
    """
    key = (effort or DEFAULT_EFFORT).strip().lower()
    return PROFILES.get(key, PROFILES[DEFAULT_EFFORT])


def synth_directive(profile: EffortProfile) -> str:
    """Prompt fragment that tells the synthesizer how verbose/deep to be."""
    return _SYNTH_DIRECTIVE[profile.synth_depth]
