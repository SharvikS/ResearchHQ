from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock

from researchhq.llm.providers.base import LLMResponse

# Reference paid pricing for free providers, so users can see what they'd otherwise pay.
EQUIVALENT_PRICING_PER_M_TOKENS = {
    "groq": {"input": 0.59, "output": 0.79},
    "gemini": {"input": 0.075, "output": 0.30},
    "openai": {"input": 0.15, "output": 0.60},
    "anthropic": {"input": 0.25, "output": 1.25},
    "ollama": {"input": 0.0, "output": 0.0},
}


@dataclass
class CostRecord:
    provider: str
    model: str
    stage: str
    input_tokens: int
    output_tokens: int
    actual_cost_usd: float = 0.0
    equivalent_cost_usd: float = 0.0


@dataclass
class CostTracker:
    records: list[CostRecord] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def record(self, response: LLMResponse, stage: str = "") -> None:
        pricing = EQUIVALENT_PRICING_PER_M_TOKENS.get(
            response.provider, {"input": 0.0, "output": 0.0}
        )
        equiv = (
            response.input_tokens * pricing["input"]
            + response.output_tokens * pricing["output"]
        ) / 1_000_000
        with self._lock:
            self.records.append(
                CostRecord(
                    provider=response.provider,
                    model=response.model,
                    stage=stage or "unknown",
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    actual_cost_usd=0.0,
                    equivalent_cost_usd=equiv,
                )
            )

    def summary(self) -> dict:
        with self._lock:
            total_in = sum(r.input_tokens for r in self.records)
            total_out = sum(r.output_tokens for r in self.records)
            equiv = sum(r.equivalent_cost_usd for r in self.records)
            by_provider: dict[str, int] = {}
            for r in self.records:
                by_provider[r.provider] = by_provider.get(r.provider, 0) + 1
            return {
                "calls": len(self.records),
                "input_tokens": total_in,
                "output_tokens": total_out,
                "actual_cost_usd": 0.0,
                "equivalent_paid_cost_usd": round(equiv, 4),
                "calls_by_provider": by_provider,
            }

    def by_stage(self) -> dict[str, dict]:
        """Per-stage rollup (calls, tokens, equivalent cost)."""
        with self._lock:
            agg: dict[str, dict] = {}
            for r in self.records:
                row = agg.setdefault(
                    r.stage,
                    {"calls": 0, "input_tokens": 0, "output_tokens": 0, "equivalent_paid_cost_usd": 0.0},
                )
                row["calls"] += 1
                row["input_tokens"] += r.input_tokens
                row["output_tokens"] += r.output_tokens
                row["equivalent_paid_cost_usd"] += r.equivalent_cost_usd
            for row in agg.values():
                row["equivalent_paid_cost_usd"] = round(row["equivalent_paid_cost_usd"], 4)
            return agg

    def reset_for_run(self) -> None:
        """Drop all prior records — called at the start of every CLI run."""
        with self._lock:
            self.records.clear()

    # Back-compat alias.
    def reset(self) -> None:
        self.reset_for_run()


tracker = CostTracker()
