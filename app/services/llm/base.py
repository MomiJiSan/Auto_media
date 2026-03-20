from abc import ABC, abstractmethod
from typing import Optional, Tuple


class BaseLLMProvider(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    async def complete(self, system: str, user: str, temperature: float = 0.3) -> str:
        """Send a prompt and return the text response."""
        ...

    @abstractmethod
    async def complete_with_usage(
        self, system: str, user: str, temperature: float = 0.3
    ) -> Tuple[str, dict]:
        """
        Send a prompt and return both text response and usage information.

        Returns:
            Tuple[str, dict]: (text_response, {"prompt_tokens": int, "completion_tokens": int})
        """
        ...
