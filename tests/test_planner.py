"""Planner tests focus on structure, not LLM behavior. We exercise:
- the JSON extractor
- the template fallback when LLM is unreachable
"""

import asyncio

import pytest

from researchhq.agents import planner
from researchhq.agents.planner import _extract_json, _fallback
from researchhq.modes import get_mode
from researchhq.reports.schema import ResearchPlan


def test_extract_json_finds_object_in_noisy_output():
    text = "junk text\n```json\n{\"queries\": [\"a\", \"b\"], \"rationale\": \"x\"}\n```"
    data = _extract_json(text)
    assert data["queries"] == ["a", "b"]


def test_extract_json_raises_when_absent():
    with pytest.raises(ValueError):
        _extract_json("no json here")


def test_template_fallback_returns_seed_queries():
    mode = get_mode("topic")
    plan = _fallback(mode, "AI agents in cybersecurity")
    assert isinstance(plan, ResearchPlan)
    assert len(plan.queries) >= 3
    assert all("cybersecurity" in q.lower() for q in plan.queries)


def test_planner_falls_back_when_llm_errors(monkeypatch):
    """If the LLM raises, planner.plan() must still return a valid ResearchPlan."""
    async def _boom(*args, **kwargs):
        raise RuntimeError("no providers")
    monkeypatch.setattr(planner.router, "complete", _boom)

    mode = get_mode("company")
    plan = asyncio.run(planner.plan(mode, "Supabase"))
    assert isinstance(plan, ResearchPlan)
    assert plan.queries  # non-empty
