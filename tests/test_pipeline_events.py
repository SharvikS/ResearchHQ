"""Pipeline emits the expected typed events at the right stages."""

from __future__ import annotations

import asyncio
import json

from researchhq.agents.fetcher import FetchedPage
from researchhq.events import PipelineEvent
from researchhq.llm.providers.base import LLMResponse
from researchhq.search.web_search import SearchResult


def _mock_router(replies: dict[str, str]):
    from researchhq.llm.cost_tracker import tracker

    class _R:
        async def complete(self, prompt, system=None, max_tokens=2048,
                           prefer=None, timeout=None, attempts=None, stage="llm"):
            text = replies.get(stage, "{}")
            resp = LLMResponse(text=text, model="mock", provider="mock",
                               input_tokens=10, output_tokens=20)
            tracker.record(resp, stage=stage)
            return resp
    return _R()


def _setup(monkeypatch):
    from researchhq.agents import (
        searcher, fetcher, planner, extractor, synthesizer,
        formatter as fmt_agent,
    )

    async def _mock_search(queries, **kwargs):
        return [
            SearchResult(title="BBC", url="https://www.bbc.com/x", snippet="A"),
            SearchResult(title="Reuters", url="https://www.reuters.com/y", snippet="B"),
            SearchResult(title="WSJ", url="https://www.wsj.com/z", snippet="C"),
        ]

    async def _mock_fetch(sources, **kwargs):
        return [
            FetchedPage(url=s.url, title=s.title, text="page content",
                        status=200, bytes_in=10, truncated=False)
            for s in sources[:8]
        ]

    monkeypatch.setattr(searcher, "search_all", _mock_search)
    monkeypatch.setattr(fetcher, "fetch_top", _mock_fetch)

    replies = {
        "planner": json.dumps({"queries": ["q1", "q2"], "rationale": ""}),
        "extractor": json.dumps({"facts": [
            {"claim": "X", "evidence_urls": ["https://www.bbc.com/x"], "confidence": 0.85}]}),
        "synthesizer": "## Executive summary\nBody [BBC](https://www.bbc.com/x).\n",
        "formatter": json.dumps({"questions": ["q?"]}),
    }
    r = _mock_router(replies)
    for mod in (planner, extractor, synthesizer, fmt_agent):
        monkeypatch.setattr(mod, "router", r)


def test_pipeline_emits_run_started_and_completed(monkeypatch):
    _setup(monkeypatch)
    events: list[PipelineEvent] = []
    from researchhq.pipeline import run as pipeline_run

    asyncio.run(pipeline_run("topic", "test query", on_event=events.append))
    types = [e.type for e in events]
    assert types[0] == "run_started"
    assert types[-1] == "run_completed"
    completed = events[-1]
    assert completed.data["llm_calls"] >= 4  # planner + extractor + synth + formatter


def test_pipeline_emits_per_agent_started_and_finished(monkeypatch):
    _setup(monkeypatch)
    events: list[PipelineEvent] = []
    from researchhq.pipeline import run as pipeline_run
    asyncio.run(pipeline_run("topic", "q", on_event=events.append))

    expected_stages = [
        "planner", "searcher", "source_ranker", "fetcher",
        "extractor", "synthesizer", "verifier", "formatter",
    ]
    started = {e.stage for e in events if e.type == "agent_started"}
    finished = {e.stage for e in events if e.type == "agent_finished"}
    for s in expected_stages:
        assert s in started, f"missing agent_started for {s}"
        assert s in finished, f"missing agent_finished for {s}"


def test_pipeline_emits_source_found_for_each_search_result(monkeypatch):
    _setup(monkeypatch)
    events: list[PipelineEvent] = []
    from researchhq.pipeline import run as pipeline_run
    asyncio.run(pipeline_run("topic", "q", on_event=events.append))
    found = [e for e in events if e.type == "source_found"]
    assert len(found) == 3
    assert all("url" in e.data for e in found)


def test_pipeline_emits_llm_call_finished_with_token_data(monkeypatch):
    _setup(monkeypatch)
    events: list[PipelineEvent] = []
    from researchhq.pipeline import run as pipeline_run
    asyncio.run(pipeline_run("topic", "q", on_event=events.append))
    llm = [e for e in events if e.type == "llm_call_finished"]
    assert llm
    assert all(e.data.get("input_tokens", 0) > 0 for e in llm)
    assert {"planner", "extractor", "synthesizer", "formatter"}.issubset(
        {e.data.get("stage_tag") for e in llm}
    )


def test_pipeline_emits_report_section_ready(monkeypatch):
    _setup(monkeypatch)
    events: list[PipelineEvent] = []
    from researchhq.pipeline import run as pipeline_run
    asyncio.run(pipeline_run("topic", "q", on_event=events.append))
    sections = [e for e in events if e.type == "report_section_ready"]
    assert sections
    assert any("executive" in e.data.get("heading", "").lower() for e in sections)
