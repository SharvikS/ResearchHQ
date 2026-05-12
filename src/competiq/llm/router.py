import logging

from competiq.config import settings
from competiq.llm.cost_tracker import tracker
from competiq.llm.providers.base import LLMProvider, LLMResponse
from competiq.llm.providers.gemini_provider import GeminiProvider
from competiq.llm.providers.groq_provider import GroqProvider
from competiq.llm.providers.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)


class LLMRouter:
    """Try providers in order; fall back on failure. Track tokens per call."""

    def __init__(self) -> None:
        self.providers: list[LLMProvider] = []
        if settings.groq_api_key:
            self.providers.append(GroqProvider(settings.groq_api_key, settings.groq_model))
        if settings.gemini_api_key:
            self.providers.append(GeminiProvider(settings.gemini_api_key, settings.gemini_model))
        # Ollama is appended unconditionally as a local fallback. If it isn't
        # actually running, the call will fail at request time and the router
        # will have already exhausted the upstream providers.
        self.providers.append(OllamaProvider(settings.ollama_host, settings.ollama_model))

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2048,
        prefer: str | None = None,
    ) -> LLMResponse:
        if not self.providers:
            raise RuntimeError(
                "No LLM providers available. Set GROQ_API_KEY or GEMINI_API_KEY in .env, "
                "or install and run Ollama."
            )

        ordered = self._ordered_providers(prefer)
        last_error: Exception | None = None
        for provider in ordered:
            try:
                response = await provider.complete(prompt, system=system, max_tokens=max_tokens)
                tracker.record(response)
                logger.info(
                    "LLM ok via %s (%d in, %d out)",
                    provider.name,
                    response.input_tokens,
                    response.output_tokens,
                )
                return response
            except Exception as e:
                logger.warning("Provider %s failed: %s. Trying next.", provider.name, e)
                last_error = e
        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    def _ordered_providers(self, prefer: str | None) -> list[LLMProvider]:
        if prefer is None:
            return self.providers
        preferred = [p for p in self.providers if p.name == prefer]
        rest = [p for p in self.providers if p.name != prefer]
        return preferred + rest


router = LLMRouter()
