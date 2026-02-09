from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseLLMAdapter(ABC):
    provider: str = "unknown"

    @property
    def capabilities(self) -> Dict[str, Any]:
        return {}

    @abstractmethod
    def build_chat_model(self):
        """Return a LangChain-compatible chat model instance."""
        raise NotImplementedError
