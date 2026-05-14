"""Query Understanding Agent — classifies user intent, domain, and complexity.

Fast and deterministic (temp=0.1). Uses the cheapest/fastest available model.
Degrades gracefully to keyword heuristics if the LLM is unavailable or returns
malformed output. The result drives pipeline slot selection and provider ordering.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Literal

from researchhq.llm.router import router

logger = logging.getLogger(__name__)

IntentType = Literal["factual", "analytical", "technical", "creative", "comparative"]
PipelineMode = Literal["fast", "balanced", "deep"]


@dataclass
class QueryIntent:
    original_query: str
    normalized_query: str
    intent_type: IntentType = "analytical"
    domain: str = "general"
    complexity: int = 3          # 1–5 scale
    requires_web_search: bool = False
    requires_code_analysis: bool = False
    requires_deep_reasoning: bool = False
    sub_questions: list[str] = field(default_factory=list)
    time_sensitive: bool = False
    ambiguity_score: float = 0.3  # 0.0 = crystal clear, 1.0 = very ambiguous
    clarification_needed: bool = False
    recommended_pipeline_mode: PipelineMode = "balanced"
    preferred_providers: list[str] = field(default_factory=list)


_SYSTEM = """You are a query classification specialist. Analyze the user query and return JSON only.

Output STRICTLY as JSON (no markdown fences, no prose):
{
  "intent_type": "factual|analytical|technical|creative|comparative",
  "domain": "science|technology|history|finance|health|law|code|politics|general|other",
  "complexity": 3,
  "requires_web_search": false,
  "requires_code_analysis": false,
  "requires_deep_reasoning": false,
  "time_sensitive": false,
  "ambiguity_score": 0.2,
  "clarification_needed": false,
  "sub_questions": [],
  "recommended_pipeline_mode": "fast|balanced|deep"
}

Complexity scale:
  1 = simple definition or single fact
  2 = straightforward explanation, one topic
  3 = multi-faceted analysis or comparison
  4 = deep research, policy, multi-step reasoning
  5 = open-ended, philosophical, highly contested

Rules:
  requires_web_search → true if query likely needs live or recent data (news, prices, current events)
  requires_code_analysis → true if query involves programming, debugging, algorithms, architecture
  requires_deep_reasoning → true if complexity >= 4 or query is philosophical/ethical
  time_sensitive → true if answer changes week-to-week (prices, news, sports)
  recommended_pipeline_mode: fast=complexity 1-2, balanced=complexity 3, deep=complexity 4-5"""


_CODE_KEYWORDS = frozenset({
    "code", "function", "debug", "error", "bug", "api", "library", "algorithm",
    "python", "javascript", "typescript", "java", "rust", "golang", "sql",
    "docker", "kubernetes", "git", "regex", "async", "thread", "memory leak",
    "exception", "stack overflow", "implement", "refactor", "class", "loop",
})

_TIME_KEYWORDS = frozenset({
    "today", "current", "latest", "recent", "now", "this week", "this year",
    "price", "stock", "news", "happening", "update", "2024", "2025", "2026",
    "trending", "right now", "live",
})

_DEEP_KEYWORDS = frozenset({
    "why", "should", "ethics", "moral", "philosophy", "future", "implications",
    "consequences", "policy", "society", "better", "worse", "meaning",
})


def _heuristic_fallback(query: str) -> QueryIntent:
    """Keyword-based classification used when LLM is unavailable."""
    normalized = " ".join(query.strip().split())
    words = frozenset(normalized.lower().split())

    requires_code = bool(_CODE_KEYWORDS & words)
    time_sensitive = bool(_TIME_KEYWORDS & words)
    requires_deep = bool(_DEEP_KEYWORDS & words)

    # Rough complexity from query length and question word presence
    word_count = len(normalized.split())
    complexity = min(5, max(1, word_count // 8 + 2))
    if requires_deep:
        complexity = max(complexity, 4)
    if time_sensitive:
        complexity = max(complexity, 2)

    intent: IntentType = (
        "technical" if requires_code
        else "analytical" if complexity >= 3
        else "factual"
    )
    domain = "code" if requires_code else "general"
    mode: PipelineMode = (
        "fast" if complexity <= 2
        else "deep" if complexity >= 4
        else "balanced"
    )

    return QueryIntent(
        original_query=query,
        normalized_query=normalized,
        intent_type=intent,
        domain=domain,
        complexity=complexity,
        requires_web_search=time_sensitive,
        requires_code_analysis=requires_code,
        requires_deep_reasoning=requires_deep,
        time_sensitive=time_sensitive,
        recommended_pipeline_mode=mode,
        preferred_providers=_providers_for(intent, complexity, requires_code),
    )


def _providers_for(intent: str, complexity: int, requires_code: bool) -> list[str]:
    """Ordered provider preference list for the pipeline router."""
    if requires_code or intent == "technical":
        return ["anthropic", "openai", "groq", "gemini", "ollama"]
    if complexity >= 4:
        return ["anthropic", "openai", "gemini", "groq", "ollama"]
    if complexity <= 2:
        return ["groq", "gemini", "ollama", "openai", "anthropic"]
    return ["groq", "gemini", "openai", "anthropic", "ollama"]


async def classify(query: str) -> QueryIntent:
    """Classify query intent. Never raises — falls back to heuristics on any error."""
    normalized = " ".join(query.strip().split())

    try:
        response = await router.complete(
            prompt=f"Classify this query: {normalized}",
            system=_SYSTEM,
            max_tokens=350,
            stage="query_understanding",
        )
        raw = response.text.strip()

        # Strip markdown fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("no JSON object in classification output")
        data = json.loads(match.group())

        complexity = max(1, min(5, int(data.get("complexity", 3))))
        raw_mode = data.get("recommended_pipeline_mode", "balanced")
        mode: PipelineMode = raw_mode if raw_mode in ("fast", "balanced", "deep") else "balanced"

        intent = data.get("intent_type", "analytical")
        requires_code = bool(data.get("requires_code_analysis", False))

        return QueryIntent(
            original_query=query,
            normalized_query=normalized,
            intent_type=intent,
            domain=str(data.get("domain", "general")),
            complexity=complexity,
            requires_web_search=bool(data.get("requires_web_search", False)),
            requires_code_analysis=requires_code,
            requires_deep_reasoning=bool(data.get("requires_deep_reasoning", False)),
            sub_questions=list(data.get("sub_questions", [])),
            time_sensitive=bool(data.get("time_sensitive", False)),
            ambiguity_score=float(data.get("ambiguity_score", 0.3)),
            clarification_needed=bool(data.get("clarification_needed", False)),
            recommended_pipeline_mode=mode,
            preferred_providers=_providers_for(intent, complexity, requires_code),
        )

    except Exception as e:
        logger.warning("Query understanding LLM failed (%s); using heuristics.", e)
        return _heuristic_fallback(normalized)
