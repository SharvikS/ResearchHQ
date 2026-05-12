"""End-to-end pipeline test with mocked search + LLM + fetcher.

The pipeline runs without network access; we hard-assert that:
- the report schema is fully populated
- citations in section bodies reference only known URLs
- the verifier's citation rule fails when the LLM emitted an invented URL
- per-stage cost stats are emitted
- the news-mode multi-source rule flags single-source claims as unconfirmed
"""

from __future__ import annotations

import asyncio
import json

import pytest

from researchhq.agents.fetcher import FetchedPage
from researchhq.llm.providers.base import LLMResponse
from researchhq.search.web_search import SearchResult


# --------------- fixtures: mocked search + LLM + fetcher ---------------------


def _make_mock_search(results: list[SearchResult]):
    async def _mock(queries, **kwargs):  # signature matches searcher.search_all
        return list(results)
    return _mock


def _make_mock_router(reply_for_stage: dict[str, str]):
    """Returns an object whose .complete() returns canned text per stage AND records cost."""
    from researchhq.llm.cost_tracker import tracker

    class _Router:
        async def complete(self, prompt, system=None, max_tokens=2048,
                           prefer=None, timeout=None, attempts=None, stage="llm"):
            text = reply_for_stage.get(stage, "{}")
            resp = LLMResponse(
                text=text, model="mock", provider="mock",
                input_tokens=10, output_tokens=20,
            )
            tracker.record(resp, stage=stage)
            return resp

    return _Router()


def _make_mock_fetcher(pages_by_url: dict[str, str]):
    async def _mock(sources, **kwargs):
        return [
            FetchedPage(
                url=s.url, title=s.title, text=pages_by_url.get(s.url, ""),
                status=200 if pages_by_url.get(s.url) else 0,
                bytes_in=len(pages_by_url.get(s.url, "")),
                truncated=False,
            )
            for s in sources[:8]
        ]
    return _mock


# --------------- e2e tests ---------------------------------------------------


def _run(mode, monkeypatch, search_results, llm_replies, fetched_pages):
    from researchhq.agents import (
        searcher,
        fetcher,
        planner,
        extractor,
        synthesizer,
        formatter as fmt_agent,
        verifier as v_mod,
    )
    from researchhq.llm import cost_tracker
    from researchhq import pipeline as pl

    # Mock search
    monkeypatch.setattr(searcher, "search_all", _make_mock_search(search_results))

    # Mock fetcher
    monkeypatch.setattr(fetcher, "fetch_top", _make_mock_fetcher(fetched_pages))

    # Mock router across all agents that use it
    mock_router = _make_mock_router(llm_replies)
    monkeypatch.setattr(planner, "router", mock_router)
    monkeypatch.setattr(extractor, "router", mock_router)
    monkeypatch.setattr(synthesizer, "router", mock_router)
    monkeypatch.setattr(fmt_agent, "router", mock_router)

    # Mock cost tracker so calls land in records (mock provider not in pricing table; that's fine)
    cost_tracker.tracker.reset_for_run()
    # Patch tracker.record to also tag stage from kwargs (it already does via router signature).

    return asyncio.run(pl.run(mode, "test query"))


def test_e2e_topic_clean_run(monkeypatch):
    search_results = [
        SearchResult(title="BBC article", url="https://www.bbc.com/news/x", snippet="A real news article"),
        SearchResult(title="ArXiv paper", url="https://arxiv.org/abs/1", snippet="An academic paper"),
        SearchResult(title="GitHub repo", url="https://github.com/foo/bar", snippet="A repo"),
    ]
    fetched = {
        "https://www.bbc.com/news/x": "Full article text from BBC about the topic.",
        "https://arxiv.org/abs/1": "Abstract of paper.",
        "https://github.com/foo/bar": "README contents.",
    }
    llm_replies = {
        "planner": json.dumps({"queries": ["test a", "test b"], "rationale": "split"}),
        "extractor": json.dumps({
            "facts": [
                {"claim": "Topic exists",
                 "evidence_urls": ["https://www.bbc.com/news/x"],
                 "confidence": 0.85},
            ]
        }),
        "synthesizer": (
            "## Executive summary\nThe topic is real per [BBC](https://www.bbc.com/news/x).\n"
            "## Key findings\n- Finding A [arxiv](https://arxiv.org/abs/1)\n"
        ),
        "formatter": json.dumps({"questions": ["What next?", "Sample size?"]}),
    }

    report = _run("topic", monkeypatch, search_results, llm_replies, fetched)

    # Schema fully populated
    assert report.mode == "topic"
    assert len(report.sources) >= 3
    assert any(p.chars > 0 for p in report.fetched_pages)
    assert report.facts and report.sections and report.verifier
    assert report.next_questions

    # Per-stage cost present
    stages = {sc.stage for sc in report.stage_costs}
    assert {"planner", "extractor", "synthesizer", "formatter"}.issubset(stages)

    # No citation violations expected — all links resolve to known URLs
    assert report.verifier.violations == []
    failed = [r for r in report.verifier.rules if not r.passed]
    failed_names = {r.name for r in failed}
    assert "citations.all_known_urls" not in failed_names


def test_e2e_invented_url_in_synth_is_stripped_and_flagged(monkeypatch):
    search_results = [
        SearchResult(title="BBC", url="https://www.bbc.com/news/x", snippet="news"),
        SearchResult(title="Reuters", url="https://www.reuters.com/y", snippet="news"),
        SearchResult(title="WSJ", url="https://www.wsj.com/z", snippet="news"),
    ]
    fetched = {url: "content" for url in [s.url for s in search_results]}
    llm_replies = {
        "planner": json.dumps({"queries": ["q"], "rationale": ""}),
        "extractor": json.dumps({"facts": [
            {"claim": "Real claim",
             "evidence_urls": ["https://www.bbc.com/news/x"],
             "confidence": 0.85},
        ]}),
        "synthesizer": (
            "## Executive summary\nA claim per [BBC](https://www.bbc.com/news/x) "
            "and another per [INVENTED](https://totally-fake.example/abc).\n"
            "## Key findings\n- See [also fake](https://another.fake/xyz)\n"
        ),
        "formatter": json.dumps({"questions": ["q1"]}),
    }
    report = _run("topic", monkeypatch, search_results, llm_replies, fetched)

    # No invented URLs survive into the rendered sections.
    body = "\n".join(s.body for s in report.sections)
    assert "totally-fake.example" not in body
    assert "another.fake" not in body
    # Invented citations recorded as violations.
    assert len(report.verifier.violations) >= 2
    assert any(v.kind == "synth.unknown_url" for v in report.verifier.violations)
    # Citation rule fails.
    failed = [r for r in report.verifier.rules if not r.passed]
    assert any(r.name == "citations.all_known_urls" for r in failed)


def test_e2e_invented_url_in_extractor_demotes_confidence(monkeypatch):
    search_results = [
        SearchResult(title="BBC", url="https://www.bbc.com/news/x", snippet="news"),
        SearchResult(title="Reuters", url="https://www.reuters.com/y", snippet="news"),
        SearchResult(title="WSJ", url="https://www.wsj.com/z", snippet="news"),
    ]
    fetched = {url: "content" for url in [s.url for s in search_results]}
    llm_replies = {
        "planner": json.dumps({"queries": ["q"], "rationale": ""}),
        "extractor": json.dumps({"facts": [
            {"claim": "Hallucinated claim",
             "evidence_urls": ["https://total.hallucination/foo"],
             "confidence": 0.95},
        ]}),
        "synthesizer": "## Executive summary\nNothing.\n",
        "formatter": json.dumps({"questions": ["q1"]}),
    }
    report = _run("topic", monkeypatch, search_results, llm_replies, fetched)

    # The single fact had only a hallucinated URL → confidence demoted to 0.5.
    assert report.facts[0].confidence == 0.5
    assert any(v.kind == "extractor.no_evidence" for v in report.verifier.violations)


def test_e2e_news_single_source_flagged_unconfirmed(monkeypatch):
    search_results = [
        SearchResult(title="BBC", url="https://www.bbc.com/news/x", snippet="news"),
        SearchResult(title="Reuters", url="https://www.reuters.com/y", snippet="news"),
        SearchResult(title="WSJ", url="https://www.wsj.com/z", snippet="news"),
    ]
    fetched = {url: "content" for url in [s.url for s in search_results]}
    llm_replies = {
        "planner": json.dumps({"queries": ["q"], "rationale": ""}),
        "extractor": json.dumps({"facts": [
            {"claim": "OpenAI announced product Z today",
             "evidence_urls": ["https://www.bbc.com/news/x"],  # only ONE news source
             "confidence": 0.9},
        ]}),
        "synthesizer": "## Executive summary\nClaim per [BBC](https://www.bbc.com/news/x).\n",
        "formatter": json.dumps({"questions": ["q1"]}),
    }
    report = _run("news", monkeypatch, search_results, llm_replies, fetched)

    failed = [r for r in report.verifier.rules if not r.passed]
    failed_names = {r.name for r in failed}
    assert "news.multi_source_corroboration" in failed_names


def test_e2e_news_multi_source_passes(monkeypatch):
    search_results = [
        SearchResult(title="BBC", url="https://www.bbc.com/news/x", snippet="news"),
        SearchResult(title="Reuters", url="https://www.reuters.com/y", snippet="news"),
        SearchResult(title="WSJ", url="https://www.wsj.com/z", snippet="news"),
    ]
    fetched = {url: "content" for url in [s.url for s in search_results]}
    llm_replies = {
        "planner": json.dumps({"queries": ["q"], "rationale": ""}),
        "extractor": json.dumps({"facts": [
            {"claim": "OpenAI announced product Z",
             "evidence_urls": [
                 "https://www.bbc.com/news/x",
                 "https://www.reuters.com/y",
             ],
             "confidence": 0.9},
        ]}),
        "synthesizer": "## Executive summary\nClaim per [BBC](https://www.bbc.com/news/x).\n",
        "formatter": json.dumps({"questions": ["q1"]}),
    }
    report = _run("news", monkeypatch, search_results, llm_replies, fetched)

    failed_names = {r.name for r in report.verifier.rules if not r.passed}
    assert "news.multi_source_corroboration" not in failed_names
