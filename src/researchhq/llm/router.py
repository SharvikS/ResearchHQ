"""LLM router — modular: tries providers in fallback order with retry+timeout.

Stage attribution: callers may either pass `stage=` to `complete()` or set the
`current_stage` ContextVar so cost records get tagged automatically.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from researchhq.config import settings
from researchhq.llm.cost_tracker import tracker
from researchhq.llm.providers.base import LLMProvider, LLMResponse
from researchhq.utils.retry import with_retry

logger = logging.getLogger(__name__)

# Per-call timeouts. Synthesizer is allowed more wall time than planner.
DEFAULT_TIMEOUT_S = 45.0
DEFAULT_ATTEMPTS = 2

# When a provider 413s / rate-limits, skip it entirely for this many seconds.
# Groq's free-tier TPM window is rolling-1-minute, so 60s is a tight match.
RATE_LIMIT_COOLDOWN_S = 60.0

# Substrings that mark an error as "rate-limited / over quota" so we know to
# cool-down the provider rather than just retry.
_RATE_LIMIT_MARKERS = (
    "rate_limit",
    "rate limit",
    "rate-limit",
    "tokens per minute",
    "tpm",
    "request too large",
    "quota",
    "429",
    "413",
    "too many requests",
)

current_stage: ContextVar[str] = ContextVar("current_stage", default="")


def _looks_rate_limited(err: BaseException) -> bool:
    """Return True if `err` looks like a rate-limit / over-quota response."""
    msg = str(err).lower()
    return any(marker in msg for marker in _RATE_LIMIT_MARKERS)


@contextmanager
def stage(name: str) -> Iterator[None]:
    token = current_stage.set(name)
    try:
        yield
    finally:
        current_stage.reset(token)


def _build_provider(name: str) -> LLMProvider | None:
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
            return OllamaProvider(settings.ollama_host, model)
    except Exception as e:
        logger.debug("Provider %s unavailable: %s", name, e)
    return None


class LLMRouter:
    def __init__(self) -> None:
        seen: set[str] = set()
        chain: list[str] = []
        for n in [settings.default_provider, *settings.fallback_chain]:
            n = n.lower()
            if n not in seen:
                seen.add(n)
                chain.append(n)
        self.providers: list[LLMProvider] = []
        for n in chain:
            p = _build_provider(n)
            if p is not None:
                self.providers.append(p)
        # Provider name -> monotonic time at which the provider becomes
        # eligible again. If now() < cooldown_until[name], that provider is
        # skipped entirely (we go straight to the next one in the chain).
        self._cooldown_until: dict[str, float] = {}

    def is_cooling_down(self, provider_name: str) -> bool:
        until = self._cooldown_until.get(provider_name.lower(), 0.0)
        return time.monotonic() < until

    def cooldown_remaining(self, provider_name: str) -> float:
        until = self._cooldown_until.get(provider_name.lower(), 0.0)
        return max(0.0, until - time.monotonic())

    def mark_rate_limited(self, provider_name: str, *, seconds: float = RATE_LIMIT_COOLDOWN_S) -> None:
        self._cooldown_until[provider_name.lower()] = time.monotonic() + seconds
        logger.warning(
            "Provider %s rate-limited; cooling down for %.0fs (next call skips this provider).",
            provider_name, seconds,
        )

    def clear_cooldowns(self) -> None:
        self._cooldown_until.clear()

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2048,
        prefer: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        attempts: int = DEFAULT_ATTEMPTS,
        stage: str | None = None,
    ) -> LLMResponse:
        if not self.providers:
            raise RuntimeError(
                "No LLM providers available. Set GROQ_API_KEY (or another provider key) "
                "in .env, or run a local Ollama."
            )

        effective_stage = stage or current_stage.get() or "llm"
        ordered = self._ordered_providers(prefer)
        last_error: Exception | None = None
        skipped_for_cooldown: list[str] = []

        for provider in ordered:
            # Sticky fallback: if this provider just got rate-limited, don't
            # waste time + budget retrying it for the next minute.
            if self.is_cooling_down(provider.name):
                skipped_for_cooldown.append(
                    f"{provider.name} ({self.cooldown_remaining(provider.name):.0f}s left)"
                )
                continue

            label = f"llm.{provider.name}.{effective_stage}"
            try:
                response = await with_retry(
                    lambda p=provider: p.complete(prompt, system=system, max_tokens=max_tokens),
                    attempts=attempts,
                    timeout=timeout,
                    label=label,
                )
                tracker.record(response, stage=effective_stage)
                logger.info(
                    "LLM ok via %s @ %s (%d in, %d out)",
                    provider.name, effective_stage,
                    response.input_tokens, response.output_tokens,
                )
                return response
            except Exception as e:  # noqa: BLE001
                if _looks_rate_limited(e):
                    self.mark_rate_limited(provider.name)
                logger.warning("Provider %s failed (%s). Trying next.", provider.name, e)
                last_error = e

        skip_note = (
            f" (skipped on cooldown: {', '.join(skipped_for_cooldown)})"
            if skipped_for_cooldown else ""
        )
        raise RuntimeError(f"All providers failed. Last error: {last_error}{skip_note}")

    def _ordered_providers(self, prefer: str | None) -> list[LLMProvider]:
        if prefer is None:
            return self.providers
        preferred = [p for p in self.providers if p.name == prefer]
        rest = [p for p in self.providers if p.name != prefer]
        return preferred + rest


router = LLMRouter()
