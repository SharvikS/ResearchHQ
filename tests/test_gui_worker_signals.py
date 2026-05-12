"""ResearchWorker translates pipeline events into Qt-friendly signals.

We test the dispatcher logic without spinning a real QThread by calling
`_handle_event` directly with synthetic PipelineEvents.
"""

from __future__ import annotations

import pytest

PySide6 = pytest.importorskip("PySide6")  # GUI tests only run when GUI extras present.

from researchhq.events import PipelineEvent
from researchhq.gui.workers.research_worker import ResearchWorker


def _make_worker():
    # parent=None is fine; we don't start the thread.
    return ResearchWorker(mode="topic", query="x")


def test_source_found_increments_counter():
    w = _make_worker()
    w._started_at = 0
    captured: list[dict] = []
    w.live_stats.connect(lambda s: captured.append(dict(s)))
    w._handle_event(PipelineEvent(type="source_found", stage="searcher",
                                  data={"url": "u1"}))
    w._handle_event(PipelineEvent(type="source_found", stage="searcher",
                                  data={"url": "u2"}))
    assert captured[-1]["sources"] == 2


def test_llm_call_finished_aggregates_tokens_and_cost():
    w = _make_worker()
    w._started_at = 0
    captured: list[dict] = []
    w.live_stats.connect(lambda s: captured.append(dict(s)))
    w._handle_event(PipelineEvent(type="llm_call_finished", stage="planner",
                                  data={"input_tokens": 100, "output_tokens": 50,
                                        "equivalent_cost_usd": 0.01}))
    w._handle_event(PipelineEvent(type="llm_call_finished", stage="extractor",
                                  data={"input_tokens": 200, "output_tokens": 80,
                                        "equivalent_cost_usd": 0.02}))
    final = captured[-1]
    assert final["llm_calls"] == 2
    assert final["input_tokens"] == 300
    assert final["output_tokens"] == 130
    assert round(final["equivalent_cost_usd"], 4) == 0.03


def test_agent_started_sets_current_agent():
    w = _make_worker()
    w._started_at = 0
    captured: list[dict] = []
    w.live_stats.connect(lambda s: captured.append(dict(s)))
    w._handle_event(PipelineEvent(type="agent_started", stage="planner"))
    assert captured[-1]["agent"] == "planner"
    w._handle_event(PipelineEvent(type="agent_started", stage="searcher"))
    assert captured[-1]["agent"] == "searcher"


def test_stage_signal_only_for_progress_events():
    w = _make_worker()
    w._started_at = 0
    stage_emits: list[tuple[str, str]] = []
    w.stage.connect(lambda s, d: stage_emits.append((s, d)))

    w._handle_event(PipelineEvent(type="agent_started", stage="planner", detail="x"))
    w._handle_event(PipelineEvent(type="source_found", stage="searcher", data={"url": "u"}))
    w._handle_event(PipelineEvent(type="run_completed", detail="done"))

    stages = [s for s, _ in stage_emits]
    assert "planner" in stages
    assert "searcher" not in stages  # source_found not a progress event
