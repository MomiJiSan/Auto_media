from app.services.llm.base import BaseLLMProvider
from app.core.config import settings

PROVIDER_MODELS = {
    "claude": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001"],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
    "qwen":   ["qwen-plus", "qwen-max", "qwen-turbo"],
    "zhipu":  ["glm-4", "glm-4-flash", "glm-3-turbo"],
    "gemini": ["gemini-2.0-flash", "gemini-2.0-pro", "gemini-1.5-flash"],
}


def get_llm_provider(
    provider: str,
    model: str | None = None,
    api_key: str = "",
    base_url: str = "",
) -> BaseLLMProvider:
    """
    Get LLM provider instance.

    Args:
        provider: Provider name (claude, openai, qwen, zhipu, gemini)
        model: Model name (optional, will use default if not provided)
        api_key: API key (optional, will use settings if not provided)
        base_url: Base URL (optional, will use settings if not provided)

    Returns:
        BaseLLMProvider instance
    """
    name = provider.lower()
    resolved_model = model or PROVIDER_MODELS[name][0]

    if name == "claude":
        from app.services.llm.claude import ClaudeProvider
        return ClaudeProvider(
            api_key=api_key or settings.anthropic_api_key,
            base_url=base_url or settings.anthropic_base_url,
            model=resolved_model
        )

    if name == "openai":
        from app.services.llm.openai import OpenAIProvider
        return OpenAIProvider(
            api_key=api_key or settings.openai_api_key,
            base_url=base_url or settings.openai_base_url,
            model=resolved_model
        )

    if name == "qwen":
        from app.services.llm.qwen import QwenProvider
        return QwenProvider(
            api_key=api_key or settings.qwen_api_key,
            base_url=base_url or settings.qwen_base_url,
            model=resolved_model
        )

    if name == "zhipu":
        from app.services.llm.zhipu import ZhipuProvider
        return ZhipuProvider(
            api_key=api_key or settings.zhipu_api_key,
            base_url=base_url or settings.zhipu_base_url,
            model=resolved_model
        )

    if name == "gemini":
        from app.services.llm.gemini import GeminiProvider
        return GeminiProvider(
            api_key=api_key or settings.gemini_api_key,
            base_url=base_url or settings.gemini_base_url,
            model=resolved_model
        )

    raise ValueError(f"Unknown LLM provider: {name}")
