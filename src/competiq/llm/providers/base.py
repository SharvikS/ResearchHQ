from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int


class LLMProvider(ABC):
    name: str

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2048,
    ) -> LLMResponse: ...
