import os

from app2.llm.base import BaseLLMAdapter
from app2.llm.gemini import GeminiAdapter


class UnsupportedProviderError(ValueError):
    pass


def get_llm_adapter(_settings=None) -> BaseLLMAdapter:
    provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if provider == "gemini":
        return GeminiAdapter()

    raise UnsupportedProviderError(f"Unsupported LLM_PROVIDER={provider}")
