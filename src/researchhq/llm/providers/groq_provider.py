from groq import AsyncGroq

from researchhq.llm.providers.base import LLMProvider, LLMResponse


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str, model: str):
        self.client = AsyncGroq(api_key=api_key)
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
