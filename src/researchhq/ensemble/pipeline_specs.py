"""Differentiated pipeline slot specifications.

Each slot defines a distinct system prompt, temperature, and preferred provider
ordering. This delivers genuine *diversity of approach*, not just different
providers running the same prompt — which is the core value-add of the
multi-agent architecture.

Slot selection logic: select_slots() maps QueryIntent → list[PipelineSlot].
Provider selection: first available provider from preferred_providers wins.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PipelineSlot = Literal[
    "fast_scan",       # Breadth-first, lightweight, enumerate key facts
    "deep_reasoning",  # Chain-of-thought, explore nuance and second-order effects
    "technical",       # Code / algorithms / architecture — precision over creativity
    "web_synthesis",   # Synthesize from web-grounded extracted facts + sources
    "extended_think",  # Extended inference chain; used for high-complexity queries
]


@dataclass
class PipelineSpec:
    slot: PipelineSlot
    name: str
    description: str
    system_prompt: str
    temperature: float
    max_tokens: int
    preferred_providers: list[str] = field(default_factory=list)


# ── System prompts ─────────────────────────────────────────────────────────────

_FAST_SCAN = """You are a research analyst optimized for speed and breadth.

Your task for this query:
1. Identify the 6–10 most important, well-established facts
2. Cover all key dimensions: what, who, when, where, how, why
3. Be concise — one clear sentence per point
4. Flag uncertain claims with [UNCERTAIN]
5. Note any areas where your knowledge may be incomplete

Format as a structured list. Prefix each point with a confidence tag:
  [CONFIRMED] — widely established fact
  [LIKELY]    — probable but less certain
  [UNCERTAIN] — claim you are not confident about"""

_DEEP_REASONING = """You are a rigorous analytical thinker. Your goal is depth, not speed.

For this query, work through the problem systematically:
1. Restate what the question is really asking (identify any hidden assumptions)
2. Identify all relevant considerations and stakeholders
3. Explore competing explanations or perspectives
4. Examine second-order effects and non-obvious implications
5. Challenge your own initial reasoning — what might you be missing?
6. Arrive at a well-grounded conclusion

Show your reasoning chain explicitly. Separate your thinking from your conclusion.
Be honest: state clearly what remains genuinely uncertain and why."""

_TECHNICAL = """You are a senior software engineer and technical domain expert.

For this technical query:
1. Provide a precise, technically accurate explanation
2. Include working, correct code examples where the query involves code
3. Identify edge cases, failure modes, and performance considerations
4. For algorithmic questions: state time and space complexity
5. Compare at least two alternative approaches with explicit tradeoffs
6. Cite specific library versions or standards where relevant

Precision over creativity. Never guess at syntax — only include code you are
certain is correct. Mark any claim you are not fully confident about with [CHECK]."""

_WEB_SYNTHESIS = """You are a research analyst synthesizing information from retrieved web sources.

You will receive extracted facts and ranked sources from a web search pipeline.
Your task:
1. Synthesize what the sources collectively say about this topic
2. Prioritize recency — for time-sensitive topics, weight newer sources more heavily
3. Identify any contradictions or disagreements between sources explicitly
4. Reference specific source numbers (e.g., [Source 3]) when making factual claims
5. Note gaps: where did the sources not answer the question?
6. Distinguish between primary sources and secondary reporting

Ground every claim in the provided sources. If a fact is not supported by the
retrieved material, explicitly flag it as "not found in sources"."""

_EXTENDED_THINK = """You are a deep analytical reasoner. Use your full capacity for extended reasoning.

For this complex query, reason exhaustively before concluding:
1. Map the full problem space — list every relevant sub-question
2. Build your inference chain step by step, making each logical move explicit
3. Consider and systematically rule out alternative hypotheses
4. Identify and test your assumptions — which ones are load-bearing?
5. Explore edge cases and boundary conditions
6. Synthesize: given all of the above, what conclusion is most supported?

Depth and rigor over speed. Show all reasoning steps. Be precise about what
your conclusion relies on. Acknowledge irreducible uncertainty honestly."""


# ── Spec registry ──────────────────────────────────────────────────────────────

PIPELINE_SPECS: dict[str, PipelineSpec] = {
    "fast_scan": PipelineSpec(
        slot="fast_scan",
        name="Fast Analysis",
        description="Breadth-first scan using the fastest available model",
        system_prompt=_FAST_SCAN,
        temperature=0.2,
        max_tokens=1024,
        preferred_providers=["groq", "gemini", "ollama", "openai", "anthropic"],
    ),
    "deep_reasoning": PipelineSpec(
        slot="deep_reasoning",
        name="Deep Reasoning",
        description="Chain-of-thought analysis with a strong reasoning model",
        system_prompt=_DEEP_REASONING,
        temperature=0.4,
        max_tokens=2048,
        preferred_providers=["anthropic", "openai", "gemini", "groq", "ollama"],
    ),
    "technical": PipelineSpec(
        slot="technical",
        name="Technical Analysis",
        description="Code and technical precision with a code-specialized model",
        system_prompt=_TECHNICAL,
        temperature=0.1,
        max_tokens=2048,
        preferred_providers=["anthropic", "openai", "groq", "gemini", "ollama"],
    ),
    "web_synthesis": PipelineSpec(
        slot="web_synthesis",
        name="Web Synthesis",
        description="Synthesizes findings from web-retrieved facts and sources",
        system_prompt=_WEB_SYNTHESIS,
        temperature=0.2,
        max_tokens=2048,
        preferred_providers=["groq", "gemini", "openai", "anthropic", "ollama"],
    ),
    "extended_think": PipelineSpec(
        slot="extended_think",
        name="Extended Reasoning",
        description="Deep inference for high-complexity or ambiguous queries",
        system_prompt=_EXTENDED_THINK,
        temperature=0.5,
        max_tokens=3000,
        preferred_providers=["anthropic", "openai", "gemini", "groq", "ollama"],
    ),
}


# ── Slot selection ─────────────────────────────────────────────────────────────

def select_slots(
    intent_type: str,
    complexity: int,
    requires_code: bool,
    requires_deep_reasoning: bool,
    mode: str,  # "fast" | "balanced" | "deep"
) -> list[str]:
    """Return ordered list of slot names to activate for this query."""
    if mode == "fast":
        return ["fast_scan", "deep_reasoning"]

    slots: list[str] = ["fast_scan", "deep_reasoning", "web_synthesis"]

    if requires_code or intent_type == "technical":
        slots.append("technical")

    if mode == "deep" or complexity >= 4 or requires_deep_reasoning:
        slots.append("extended_think")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for s in slots:
        if s not in seen:
            seen.add(s)
            unique.append(s)

    return unique[:5]  # hard cap at 5 parallel slots
