from dataclasses import dataclass, field
from threading import Lock

from competiq.llm.providers.base import LLMResponse

# All providers used here are FREE. We log tokens for benchmarking and surface
# the equivalent paid cost so reviewers can see what we'd be saving.
EQUIVALENT_PRICING_PER_M_TOKENS = {
    "groq": {"input": 0.59, "output": 0.79},      # Llama 3.3 70B reference
    "gemini": {"input": 0.075, "output": 0.30},   # Gemini 2.0 Flash reference
    "ollama": {"input": 0.0, "output": 0.0},      # Local
}


@dataclass
class CostRecord:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    actual_cost_usd: float = 0.0
    equivalent_cost_usd: float = 0.0


@dataclass
class CostTracker:
    records: list[CostRecord] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def record(self, response: LLMResponse) -> None:
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

    def reset(self) -> None:
        with self._lock:
            self.records.clear()


tracker = CostTracker()
