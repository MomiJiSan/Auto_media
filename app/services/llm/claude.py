import anthropic
from app.services.llm.base import BaseLLMProvider


class ClaudeProvider(BaseLLMProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com", model: str = "claude-sonnet-4-6"):
        self._client = anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url)
        self._model = model

    async def complete(self, system: str, user: str, temperature: float = 0.3) -> str:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text

    async def complete_with_usage(self, system: str, user: str, temperature: float = 0.3) -> tuple[str, dict]:
        msg = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        usage_obj = getattr(msg, "usage", None)
        usage = {
            "prompt_tokens": usage_obj.input_tokens if usage_obj else 0,
            "completion_tokens": usage_obj.output_tokens if usage_obj else 0,
        }
        return msg.content[0].text, usage
