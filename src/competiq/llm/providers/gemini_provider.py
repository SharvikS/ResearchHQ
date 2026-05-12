from google import genai

from competiq.llm.providers.base import LLMProvider, LLMResponse


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        resp = await self.client.aio.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config={"max_output_tokens": max_tokens},
        )
        usage = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            text=resp.text or "",
            model=self.model,
            provider=self.name,
            input_tokens=getattr(usage, "prompt_token_count", 0) if usage else 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) if usage else 0,
        )
