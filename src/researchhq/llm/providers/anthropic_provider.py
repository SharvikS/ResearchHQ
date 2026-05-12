"""Anthropic provider stub — deferred import like OpenAI."""

from researchhq.llm.providers.base import LLMProvider, LLMResponse


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str):
        try:
            from anthropic import AsyncAnthropic
        except ImportError as e:
            raise RuntimeError(
                "Anthropic provider requested but `anthropic` package is not installed. "
                "Install with: pip install anthropic"
            ) from e
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        resp = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=text,
            model=self.model,
            provider=self.name,
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
        )
