import os

from langchain_google_genai import ChatGoogleGenerativeAI

from .mock_llm import (
    DEFAULT_TEMPERATURE,
    LLMConfig,
    MOCK_CONFIG,
    MODEL_NAME,
    MockLLM,
)

GEMINI_MODEL = "gemini-3.6-flash"


class GeminiLLM:
    def __init__(self):
        if not os.getenv("GOOGLE_API_KEY"):
            raise RuntimeError("GOOGLE_API_KEY is not set")

        self.llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            temperature=DEFAULT_TEMPERATURE,
        )
        self.config = LLMConfig(
            provider="gemini",
            model=GEMINI_MODEL,
            temperature=DEFAULT_TEMPERATURE,
        )

    def invoke(self, prompt):
        return self.llm.invoke(prompt)


def provider_name() -> str:
    return (os.getenv("AGENTFAULT_LLM") or "mock").strip().lower()


def make_llm(provider: str | None = None):
    name = (provider or provider_name()).lower()

    if name == "mock":
        return MockLLM()

    if name == "gemini":
        return GeminiLLM()

    raise ValueError(
        f"Unknown LLM provider {name!r}; expected 'mock' or 'gemini'"
    )


def active_config(provider: str | None = None) -> LLMConfig:
    name = (provider or provider_name()).lower()

    if name == "mock":
        return MOCK_CONFIG

    if name == "gemini":
        return LLMConfig(
            provider="gemini",
            model=GEMINI_MODEL,
            temperature=DEFAULT_TEMPERATURE,
        )

    raise ValueError(
        f"Unknown LLM provider {name!r}; expected 'mock' or 'gemini'"
    )
