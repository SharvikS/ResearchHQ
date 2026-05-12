from competiq.llm.cost_tracker import CostTracker
from competiq.llm.providers.base import LLMResponse


def test_records_aggregate_per_provider():
    t = CostTracker()
    t.record(LLMResponse(text="x", model="m1", provider="groq", input_tokens=100, output_tokens=200))
    t.record(LLMResponse(text="x", model="m2", provider="gemini", input_tokens=50, output_tokens=80))
    t.record(LLMResponse(text="x", model="m1", provider="groq", input_tokens=10, output_tokens=20))

    s = t.summary()
    assert s["calls"] == 3
    assert s["input_tokens"] == 160
    assert s["output_tokens"] == 300
    assert s["actual_cost_usd"] == 0.0
    assert s["calls_by_provider"] == {"groq": 2, "gemini": 1}
    assert s["equivalent_paid_cost_usd"] > 0


def test_unknown_provider_costs_zero():
    t = CostTracker()
    t.record(LLMResponse(text="x", model="m", provider="ollama", input_tokens=1000, output_tokens=2000))
    s = t.summary()
    assert s["equivalent_paid_cost_usd"] == 0.0
