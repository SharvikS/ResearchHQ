"""Parallel multi-provider execution engine.

Builds provider instances for all configured ensemble participants and runs
them concurrently with asyncio.gather. One provider failing never aborts the
run — partial results are collected and confidence is reduced accordingly.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from researchhq.config import settings
from researchhq.llm.cost_tracker import tracker
from researchhq.llm.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

PROVIDER_TIMEOUT_S = 60.0

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
            logger.warning("Ensemble %s timed out after %.1fs", provider.name, elapsed)
        except Exception as e:  # noqa: BLE001
            elapsed = time.monotonic() - t0
            result = ProviderResult(
                provider=provider.name, model="", text="",
                elapsed=elapsed, status="error", error=str(e),
            )
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
