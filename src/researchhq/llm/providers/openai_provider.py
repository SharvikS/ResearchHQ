"""OpenAI provider stub. The `openai` SDK is intentionally optional —
the import is deferred so missing the dependency only fails when this
provider is actually selected."""

from researchhq.llm.providers.base import LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str):
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise RuntimeError(
                "OpenAI provider requested but `openai` package is not installed. "
                "Install with: pip install openai"
            ) from e
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
        )
        usage = resp.usage
        return LLMResponse(
            text=resp.choices[0].message.content or "",
            model=self.model,
            provider=self.name,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
