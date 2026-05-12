from ollama import AsyncClient

from researchhq.llm.providers.base import LLMProvider, LLMResponse


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, host: str, model: str):
        self.client = AsyncClient(host=host)
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
        resp = await self.client.chat(
            model=self.model,
            messages=messages,
            options={"num_predict": max_tokens},
        )
        return LLMResponse(
            text=resp["message"]["content"],
            model=self.model,
            provider=self.name,
            input_tokens=resp.get("prompt_eval_count", 0),
            output_tokens=resp.get("eval_count", 0),
        )
