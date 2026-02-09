import os

from langchain_google_genai import ChatGoogleGenerativeAI

from app2.llm.base import BaseLLMAdapter


class GeminiAdapter(BaseLLMAdapter):
    provider = "gemini"

    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0"))

    def build_chat_model(self):
        return ChatGoogleGenerativeAI(model=self.model, temperature=self.temperature)
