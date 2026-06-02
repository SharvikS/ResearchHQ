from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from researchhq.events import PipelineEvent
from researchhq.reports.schema import Fact, ResearchPlan, ResearchReport, Section, VerifierNote
from researchhq.search.source_quality import RankedSource, SourceTier
from researchhq.server import app as server_app


def _sample_report() -> ResearchReport:
    return ResearchReport(
        mode="topic",
        query="test query",
        plan=ResearchPlan(queries=["test query"], rationale="sample"),
        sources=[
            RankedSource(
                url="https://example.com/report",
                title="Example report",
                snippet="sample",
                tier=SourceTier.OFFICIAL,
                score=10,
                domain="example.com",
            )
        ],
        facts=[
            Fact(
                claim="ResearchHQ can return a web response.",
                evidence_urls=["https://example.com/report"],
                confidence=0.9,
            )
        ],
        sections=[
            Section(heading="Executive summary", body="ResearchHQ returned a result."),
            Section(heading="Key findings", body="- The API is wired to the pipeline."),
        ],
        verifier=VerifierNote(overall_confidence=0.82, notes=["mocked run"]),
        next_questions=["What should be improved next?"],
        provider_used="mock",
    )


def test_server_query_status_and_result(monkeypatch, tmp_path) -> None:
    async def fake_pipeline_run(mode, query, on_event=None, effort="medium"):
        assert mode == "topic"
        assert effort == "low"
        if on_event:
            on_event(PipelineEvent(type="agent_started", stage="planner", detail="planning"))
            on_event(PipelineEvent(type="agent_finished", stage="planner", detail="done"))
        await asyncio.sleep(0)
        return _sample_report()

    monkeypatch.setattr(server_app, "pipeline_run", fake_pipeline_run)
    monkeypatch.setattr(server_app.settings, "output_folder", str(tmp_path))
    server_app.RUNS.clear()

    with TestClient(server_app.app) as client:
        submitted = client.post(
            "/api/v1/query",
            json={
                "query": "test query",
                "mode": "research",
                "pipeline_mode": "fast",
                "format": "markdown",
                "options": {"ensemble_mode": "off"},
            },
        ).json()
        query_id = submitted["query_id"]

        for _ in range(20):
            status = client.get(f"/api/v1/query/{query_id}/status").json()
            if status["status"] == "complete":
                break
            asyncio.run(asyncio.sleep(0.01))

        assert status["status"] == "complete"
        assert status["progress_pct"] == 100
        assert status["pipelines"][0]["slot_name"] == "planner"

        result = client.get(f"/api/v1/query/{query_id}/result").json()
        final = result["final_response"]
        assert final["executive_summary"] == "ResearchHQ returned a result."
        assert final["confidence"]["label"] == "high"
        assert final["sources"][0]["domain"] == "example.com"

