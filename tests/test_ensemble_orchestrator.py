"""Tests for ensemble/orchestrator.py — parallel provider execution."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from researchhq.ensemble.orchestrator import (
    EnsembleRun,
    ProviderResult,
    build_ensemble_providers,
    run_parallel,
)
from researchhq.llm.providers.base import LLMResponse


def _mock_provider(name: str, response_text: str = "ok", delay: float = 0.0):
    provider = MagicMock()
    provider.name = name

    async def _complete(*_a, **_kw):
        if delay:
            await asyncio.sleep(delay)
        return LLMResponse(
            text=response_text,
            model=f"mock-{name}",
            provider=name,
            input_tokens=10,
            output_tokens=20,
        )

    provider.complete = _complete
    return provider


def _mock_failing_provider(name: str, exc: Exception = RuntimeError("api error")):
    provider = MagicMock()
    provider.name = name

    async def _complete(*_a, **_kw):
        raise exc

    provider.complete = _complete
    return provider


def _mock_timeout_provider(name: str, delay: float = 999.0):
    return _mock_provider(name, delay=delay)


# ── run_parallel ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_parallel_all_succeed():
    providers = [
        _mock_provider("groq", "groq output"),
        _mock_provider("gemini", "gemini output"),
    ]
    run = await run_parallel("prompt", "system", providers, query="q")
    assert len(run.results) == 2
    assert all(r.status == "success" for r in run.results)
    assert run.success_rate == 1.0
    assert len(run.successful) == 2
    assert len(run.failed) == 0


@pytest.mark.asyncio
async def test_run_parallel_partial_failure():
    providers = [
        _mock_provider("groq", "groq output"),
        _mock_failing_provider("openai"),
    ]
    run = await run_parallel("prompt", "system", providers, query="q")
    assert len(run.results) == 2
    assert run.results[0].status == "success"
    assert run.results[1].status == "error"
    assert len(run.successful) == 1
    assert len(run.failed) == 1
    assert run.success_rate == 0.5


@pytest.mark.asyncio
async def test_run_parallel_timeout():
    providers = [
        _mock_provider("groq", "fast output"),
        _mock_provider("slow", "slow output", delay=10.0),
    ]
    run = await run_parallel("prompt", "system", providers, query="q", timeout=0.1)
    ok = [r for r in run.results if r.status == "success"]
    timeout = [r for r in run.results if r.status == "timeout"]
    assert len(ok) == 1
    assert len(timeout) == 1
    assert ok[0].provider == "groq"


@pytest.mark.asyncio
async def test_run_parallel_empty_providers():
    run = await run_parallel("prompt", "system", [], query="q")
    assert run.results == []
    assert run.success_rate == 0.0
    assert run.successful == []


@pytest.mark.asyncio
async def test_run_parallel_all_fail():
    providers = [
        _mock_failing_provider("a"),
        _mock_failing_provider("b"),
    ]
    run = await run_parallel("prompt", "system", providers, query="q")
    assert all(r.status == "error" for r in run.results)
    assert run.successful == []
    assert len(run.failed) == 2


@pytest.mark.asyncio
async def test_run_parallel_on_provider_event_called():
    events: list[ProviderResult] = []
    providers = [_mock_provider("groq", "text")]
    await run_parallel(
        "p", "s", providers, query="q",
        on_provider_event=lambda r: events.append(r),
    )
    assert len(events) == 1
    assert events[0].provider == "groq"


@pytest.mark.asyncio
async def test_run_parallel_elapsed_recorded():
    providers = [_mock_provider("groq")]
    run = await run_parallel("p", "s", providers, query="q")
    assert run.elapsed_total >= 0.0
    assert run.results[0].elapsed >= 0.0


@pytest.mark.asyncio
async def test_ensemble_run_properties():
    run = EnsembleRun(
        query="q",
        results=[
            ProviderResult(provider="a", model="m", text="text", status="success"),
            ProviderResult(provider="b", model="m", text="", status="empty"),
            ProviderResult(provider="c", model="m", text="", status="error"),
        ],
    )
    assert len(run.successful) == 1
    assert len(run.failed) == 2
    assert run.provider_names == ["a", "b", "c"]


# ── build_ensemble_providers ──────────────────────────────────────────────────

def test_build_ensemble_providers_deduplicates(monkeypatch):
    """Duplicate names in the list should only produce one provider."""
    from researchhq.ensemble import orchestrator as orch

    def _make(name: str):
        m = MagicMock()
        m.name = name  # must set attribute directly, not via MagicMock(name=) constructor
        return m

    monkeypatch.setattr(orch, "build_provider", _make)
    providers = build_ensemble_providers(["groq", "groq", "gemini"], max_providers=5)
    names = [p.name for p in providers]
    assert names.count("groq") == 1
    assert "gemini" in names


def test_build_ensemble_providers_respects_max(monkeypatch):
    from researchhq.ensemble import orchestrator as orch
    monkeypatch.setattr(orch, "build_provider", lambda name: MagicMock(name=name))
    providers = build_ensemble_providers(["a", "b", "c", "d", "e"], max_providers=2)
    assert len(providers) <= 2


def test_build_ensemble_providers_skips_unavailable(monkeypatch):
    from researchhq.ensemble import orchestrator as orch
    monkeypatch.setattr(orch, "build_provider", lambda name: None)
    providers = build_ensemble_providers(["a", "b", "c"])
    assert providers == []
