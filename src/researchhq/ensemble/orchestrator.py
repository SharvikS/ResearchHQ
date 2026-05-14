"""Parallel multi-provider execution engine.

Builds provider instances for all configured ensemble participants and runs
them concurrently with asyncio.gather. One provider failing never aborts the
run — partial results are collected and confidence is reduced accordingly.

Two execution modes:
  run_parallel()  — legacy: same prompt/system sent to all providers
  run_slots()     — new:    each slot gets its own system prompt, temperature,
                            and preferred provider (differentiated pipelines)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from researchhq.config import settings
from researchhq.llm.circuit_breaker import get_breaker
from researchhq.llm.cost_tracker import tracker
from researchhq.llm.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

PROVIDER_TIMEOUT_S = 60.0


def _update_cb_metric(provider: str, *, is_open: bool) -> None:
    """Update the Prometheus circuit-breaker gauge without hard-wiring metrics import."""
    try:
        from researchhq.api.metrics import update_circuit_breaker_gauge
        update_circuit_breaker_gauge(provider, is_open)
    except Exception:  # noqa: BLE001 — metrics are optional; never crash the pipeline
        pass

# Provider lists by cost/quality profile
ENSEMBLE_PROFILES: dict[str, list[str]] = {
    "cheap":          ["groq", "ollama"],
    "balanced":       ["groq", "gemini", "openai"],
    "max_confidence": ["groq", "gemini", "openai", "anthropic", "ollama"],
}


@dataclass
class ProviderResult:
    provider: str
    model: str
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    elapsed: float = 0.0
    status: str = "success"    # success | timeout | error | empty
    error: Optional[str] = None


@dataclass
class EnsembleRun:
    query: str
    results: list[ProviderResult] = field(default_factory=list)
    elapsed_total: float = 0.0

    @property
    def successful(self) -> list[ProviderResult]:
        return [r for r in self.results if r.status == "success" and r.text.strip()]

    @property
    def failed(self) -> list[ProviderResult]:
        return [r for r in self.results if r.status != "success"]

    @property
    def provider_names(self) -> list[str]:
        return [r.provider for r in self.results]

    @property
    def success_rate(self) -> float:
        if not self.results:
            return 0.0
        return len(self.successful) / len(self.results)


def build_provider(name: str) -> Optional[LLMProvider]:
    """Build a provider instance by name; returns None if unavailable."""
    name = name.lower()
    model = settings.models.get(name, "")
    try:
        if name == "groq" and settings.groq_api_key:
            from researchhq.llm.providers.groq_provider import GroqProvider
            return GroqProvider(settings.groq_api_key, model)
        if name == "gemini" and settings.gemini_api_key:
            from researchhq.llm.providers.gemini_provider import GeminiProvider
            return GeminiProvider(settings.gemini_api_key, model)
        if name == "openai" and settings.openai_api_key:
            from researchhq.llm.providers.openai_provider import OpenAIProvider
            return OpenAIProvider(settings.openai_api_key, model)
        if name == "anthropic" and settings.anthropic_api_key:
            from researchhq.llm.providers.anthropic_provider import AnthropicProvider
            return AnthropicProvider(settings.anthropic_api_key, model)
        if name == "ollama":
            from researchhq.llm.providers.ollama_provider import OllamaProvider
            return OllamaProvider(settings.ollama_host, model or "llama3.2:3b")
    except Exception as e:
        logger.debug("Provider %s unavailable for ensemble: %s", name, e)
    return None


def build_ensemble_providers(
    provider_names: list[str],
    max_providers: int = 5,
) -> list[LLMProvider]:
    """Build available provider instances for the ensemble, up to max_providers."""
    providers: list[LLMProvider] = []
    seen: set[str] = set()
    for name in provider_names[:max_providers]:
        name = name.lower()
        if name in seen:
            continue
        seen.add(name)
        p = build_provider(name)
        if p is not None:
            providers.append(p)
    return providers


async def run_parallel(
    prompt: str,
    system: str,
    providers: list[LLMProvider],
    query: str,
    *,
    timeout: float = PROVIDER_TIMEOUT_S,
    max_tokens: int = 2048,
    on_provider_event: Optional[Callable[[ProviderResult], None]] = None,
) -> EnsembleRun:
    """Run all providers in parallel, collecting results independently.

    Uses asyncio.gather so one provider's timeout/error never blocks others.
    Cost tracking tags each successful response as stage="ensemble".
    """
    if not providers:
        return EnsembleRun(query=query)

    async def _run_one(provider: LLMProvider) -> ProviderResult:
        t0 = time.monotonic()
        result: ProviderResult
        breaker = get_breaker(provider.name)

        if not breaker.allow_request():
            elapsed = time.monotonic() - t0
            _update_cb_metric(provider.name, is_open=True)
            return ProviderResult(
                provider=provider.name, model="", text="",
                elapsed=elapsed, status="error",
                error="circuit breaker open — provider skipped",
            )

        try:
            response: LLMResponse = await asyncio.wait_for(
                provider.complete(prompt, system=system, max_tokens=max_tokens),
                timeout=timeout,
            )
            elapsed = time.monotonic() - t0
            status = "success" if response.text.strip() else "empty"
            result = ProviderResult(
                provider=provider.name,
                model=response.model,
                text=response.text,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                elapsed=elapsed,
                status=status,
            )
            tracker.record(response, stage="ensemble")
            breaker.record_success()
            _update_cb_metric(provider.name, is_open=False)
            logger.info(
                "Ensemble %s: %s in %.1fs (%d+%d tokens)",
                provider.name, status, elapsed,
                response.input_tokens, response.output_tokens,
            )
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - t0
            result = ProviderResult(
                provider=provider.name, model="", text="",
                elapsed=elapsed, status="timeout",
                error=f"timed out after {elapsed:.1f}s",
            )
            breaker.record_failure()
            _update_cb_metric(provider.name, is_open=breaker.is_open)
            logger.warning("Ensemble %s timed out after %.1fs", provider.name, elapsed)
        except Exception as e:  # noqa: BLE001
            elapsed = time.monotonic() - t0
            result = ProviderResult(
                provider=provider.name, model="", text="",
                elapsed=elapsed, status="error", error=str(e),
            )
            breaker.record_failure()
            _update_cb_metric(provider.name, is_open=breaker.is_open)
            logger.warning("Ensemble %s failed: %s", provider.name, e)

        if on_provider_event:
            try:
                on_provider_event(result)
            except Exception:  # noqa: BLE001
                pass
        return result

    t0 = time.monotonic()
    raw = await asyncio.gather(*[_run_one(p) for p in providers])
    elapsed_total = time.monotonic() - t0

    return EnsembleRun(
        query=query,
        results=list(raw),
        elapsed_total=elapsed_total,
    )


# ── Differentiated slot execution ──────────────────────────────────────────────


@dataclass
class SlotExecution:
    """One pipeline slot paired with its provider and specialized prompts."""
    slot_name: str           # "fast_scan", "deep_reasoning", etc.
    display_name: str        # Human-readable name for UI / logs
    provider: LLMProvider
    system_prompt: str
    user_prompt: str
    max_tokens: int = 2048
    timeout: float = PROVIDER_TIMEOUT_S


async def run_slots(
    slots: list[SlotExecution],
    query: str,
    *,
    on_slot_event: Optional[Callable[["ProviderResult"], None]] = None,
) -> "EnsembleRun":
    """Run each pipeline slot in parallel with its own system prompt and provider.

    This is the differentiated execution path: each slot thinks about the query
    from a different angle (fast breadth-first scan, deep reasoning, technical
    analysis, etc.) with the best-fit model for that role.

    Falls back silently: a failed slot contributes an error ProviderResult so
    the EnsembleRun always contains an entry per slot for progress tracking.
    """
    if not slots:
        return EnsembleRun(query=query)

    async def _run_slot(slot: SlotExecution) -> "ProviderResult":
        t0 = time.monotonic()
        slot_label = f"{slot.slot_name}({slot.provider.name})"
        breaker = get_breaker(slot.provider.name)

        if not breaker.allow_request():
            elapsed = time.monotonic() - t0
            _update_cb_metric(slot.provider.name, is_open=True)
            return ProviderResult(
                provider=slot_label, model="", text="",
                elapsed=elapsed, status="error",
                error="circuit breaker open — provider skipped",
            )

        try:
            response: LLMResponse = await asyncio.wait_for(
                slot.provider.complete(
                    slot.user_prompt,
                    system=slot.system_prompt,
                    max_tokens=slot.max_tokens,
                ),
                timeout=slot.timeout,
            )
            elapsed = time.monotonic() - t0
            status = "success" if response.text.strip() else "empty"
            result = ProviderResult(
                provider=slot_label,
                model=response.model,
                text=response.text,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                elapsed=elapsed,
                status=status,
            )
            tracker.record(response, stage=f"slot_{slot.slot_name}")
            breaker.record_success()
            _update_cb_metric(slot.provider.name, is_open=False)
            logger.info(
                "Slot %s via %s: %s in %.1fs (%d+%d tokens)",
                slot.slot_name, slot.provider.name, status, elapsed,
                response.input_tokens, response.output_tokens,
            )
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - t0
            result = ProviderResult(
                provider=slot_label, model="", text="",
                elapsed=elapsed, status="timeout",
                error=f"timed out after {elapsed:.1f}s",
            )
            breaker.record_failure()
            _update_cb_metric(slot.provider.name, is_open=breaker.is_open)
            logger.warning("Slot %s timed out after %.1fs", slot.slot_name, elapsed)
        except Exception as e:  # noqa: BLE001
            elapsed = time.monotonic() - t0
            result = ProviderResult(
                provider=slot_label, model="", text="",
                elapsed=elapsed, status="error", error=str(e),
            )
            breaker.record_failure()
            _update_cb_metric(slot.provider.name, is_open=breaker.is_open)
            logger.warning("Slot %s failed: %s", slot.slot_name, e)

        if on_slot_event:
            try:
                on_slot_event(result)
            except Exception:  # noqa: BLE001
                pass
        return result

    t0 = time.monotonic()
    raw = await asyncio.gather(*[_run_slot(s) for s in slots])
    elapsed_total = time.monotonic() - t0

    return EnsembleRun(
        query=query,
        results=list(raw),
        elapsed_total=elapsed_total,
    )


def build_slot_executions(
    slot_names: list[str],
    user_prompt: str,
    available_provider_names: Optional[list[str]] = None,
    max_tokens_override: Optional[int] = None,
    timeout: float = PROVIDER_TIMEOUT_S,
) -> list["SlotExecution"]:
    """Build SlotExecution instances, matching each slot to its best available provider.

    Each slot's preferred_providers list is tried in order; the first available
    provider wins. A slot with no available providers is silently skipped so the
    caller always gets a valid (possibly empty) list.
    """
    from researchhq.ensemble.pipeline_specs import PIPELINE_SPECS

    result: list[SlotExecution] = []
    used_providers: set[str] = set()  # prevent two slots competing for the same instance

    for slot_name in slot_names:
        spec = PIPELINE_SPECS.get(slot_name)
        if spec is None:
            logger.warning("Unknown pipeline slot %r — skipped.", slot_name)
            continue

        provider_order = (
            available_provider_names if available_provider_names is not None
            else spec.preferred_providers
        )

        provider: Optional[LLMProvider] = None
        for pname in provider_order:
            if pname in used_providers:
                continue
            p = build_provider(pname)
            if p is not None:
                provider = p
                used_providers.add(pname)
                break

        if provider is None:
            # Try any provider regardless of the "used" constraint
            for pname in spec.preferred_providers:
                p = build_provider(pname)
                if p is not None:
                    provider = p
                    break

        if provider is None:
            logger.warning("No provider available for slot %r — skipped.", slot_name)
            continue

        result.append(SlotExecution(
            slot_name=slot_name,
            display_name=spec.name,
            provider=provider,
            system_prompt=spec.system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens_override or spec.max_tokens,
            timeout=timeout,
        ))

    return result
