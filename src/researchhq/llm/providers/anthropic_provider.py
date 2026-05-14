"""Anthropic provider with optional extended thinking support."""

from researchhq.llm.providers.base import LLMProvider, LLMResponse


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str,
        thinking_budget: int = 0,
        temperature: float = 0.3,
    ):
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise RuntimeError(
                "Anthropic provider requested but `anthropic` package is not installed. "
                "Install with: pip install anthropic"
            ) from e
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        # thinking_budget > 0 enables extended thinking mode (disables temperature)
        self.thinking_budget = thinking_budget
        self.temperature = temperature

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system or "",
            "messages": [{"role": "user", "content": prompt}],
        }

        if self.thinking_budget > 0:
            # Extended thinking: temperature is not compatible — omit it
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget,
            }
        else:
            kwargs["temperature"] = self.temperature

        resp = await self.client.messages.create(**kwargs)

        # Extract only text blocks (skip thinking blocks for the public response)
        text = "".join(
            block.text
            for block in resp.content
            if getattr(block, "type", "") == "text"
        )
        thinking_tokens = sum(
            len(getattr(block, "thinking", "").split())
            for block in resp.content
            if getattr(block, "type", "") == "thinking"
        )

        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=text,
            model=self.model,
            provider=self.name,
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
        )


def make_anthropic_thinking(api_key: str, model: str, budget: int = 8000) -> AnthropicProvider:
    """Convenience factory for an Anthropic provider with extended thinking enabled."""
    return AnthropicProvider(api_key=api_key, model=model, thinking_budget=budget)
