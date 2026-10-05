"""Deterministic offline LLM used for reproducible trajectory generation.

Every response is a pure function of the prompt: no randomness, no network
access, temperature is 0 by construction. The mock follows the same tool
protocol as the Gemini prompt (respond with JSON to request a tool call).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

MODEL_NAME = "mock-llm-v1"
DEFAULT_TEMPERATURE = 0.0


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    temperature: float


MOCK_CONFIG = LLMConfig(
    provider="mock",
    model=MODEL_NAME,
    temperature=DEFAULT_TEMPERATURE,
)

_HEADERS = (
    "User query:",
    "Query:",
    "Retrieved context:",
    "Previous tool result:",
    "Research:",
    "Tool result:",
    "Review:",
)

_MATH_WORDS = (
    ("divided by", " / "),
    ("multiplied by", " * "),
    ("times", " * "),
    ("plus", " + "),
    ("minus", " - "),
)

_STATUS_KEYWORDS = ("status", "healthy", "health check", "service")

_SERVICES = ("api", "worker", "database")

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does",
    "explain", "for", "from", "how", "i", "in", "is", "it", "of", "on",
    "or", "please", "show", "summarize", "the", "to", "what", "when",
    "where", "which", "who", "why", "with", "you", "your", "current",
    "right", "now", "about", "into", "give",
}

_SUFFIXES = (
    ("ies", "y"),
    ("ing", ""),
    ("ed", ""),
    ("es", ""),
    ("s", ""),
)


class MockMessage:
    def __init__(self, content: str):
        self.content = content

    def __str__(self) -> str:
        return self.content


def _prompt_text(prompt) -> str:
    if isinstance(prompt, str):
        return prompt

    if isinstance(prompt, list):
        parts = []
        for item in prompt:
            content = getattr(item, "content", item)
            if isinstance(content, list):
                content = "".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict)
                )
            parts.append(str(content))
        return "\n".join(parts)

    return str(prompt)


def _section(prompt: str, header: str) -> str:
    lines = []
    active = False
    for line in prompt.splitlines():
        stripped = line.strip()
        if stripped in _HEADERS:
            active = stripped == header
            continue
        if active:
            lines.append(line)
    return "\n".join(lines).strip()


def _normalize_math(query: str) -> str:
    text = query.lower()
    for words, symbol in _MATH_WORDS:
        text = text.replace(words, symbol)
    return re.sub(r"\b(\d+)\s+squared\b", r"\1 ** 2", text)


def extract_expression(query: str) -> str | None:
    text = _normalize_math(query)
    match = re.search(
        r"(-?\d+(?:\.\d+)?"
        r"(?:\s*(?:\*\*|\*|/|%|\+|-)\s*-?\d+(?:\.\d+)?)+)",
        text,
    )
    if not match:
        return None

    expression = re.sub(r"\s+", " ", match.group(1).strip())
    if not re.fullmatch(r"[\d\s.*/%+-]+", expression):
        return None
    return expression


def _detect_service(query: str) -> str:
    lowered = query.lower()
    for service in _SERVICES:
        if service in lowered:
            return service
    return "api"


def decide_tool(query: str) -> dict | None:
    expression = extract_expression(query)
    if expression:
        return {
            "tool": "calculator",
            "input": {"expression": expression},
        }

    lowered = query.lower()
    if any(keyword in lowered for keyword in _STATUS_KEYWORDS):
        return {
            "tool": "get_system_status",
            "input": {"service": _detect_service(query)},
        }

    return None


def _stem(word: str) -> str:
    for suffix, replacement in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)] + replacement
    return word


def _keywords(query: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", query.lower())
    return [
        _stem(word)
        for word in words
        if word not in _STOPWORDS and len(word) > 2
    ]


def _sentences(context: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", context)
        if sentence.strip()
    ]


def grounded_answer(query: str, context: str) -> str:
    keywords = _keywords(query)
    best = None
    best_score = 0

    for sentence in _sentences(context):
        lowered = sentence.lower()
        score = sum(1 for word in keywords if word in lowered)
        if score > best_score:
            best = sentence
            best_score = score

    if best:
        return best

    return (
        "The retrieved context does not contain a direct "
        f"answer to: {query}"
    )


class MockLLM:
    config = MOCK_CONFIG

    def invoke(self, prompt) -> MockMessage:
        text = _prompt_text(prompt)

        if "reviewer sub-agent" in text:
            return MockMessage(self._review(text))

        if "Produce the final answer" in text:
            return MockMessage(self._answer(text))

        return MockMessage(self._research(text))

    def _research(self, text: str) -> str:
        query = _section(text, "User query:")
        context = _section(text, "Retrieved context:")
        tool_result = _section(text, "Previous tool result:")

        if tool_result:
            return (
                f"Findings for '{query}': tool result -> {tool_result}. "
                "The retrieved context was reviewed and does not "
                "contradict the tool evidence."
            )

        decision = decide_tool(query)
        if decision:
            return json.dumps(decision, indent=4)

        return grounded_answer(query, context)

    def _review(self, text: str) -> str:
        query = _section(text, "User query:")
        tool_result = _section(text, "Tool result:")

        if tool_result:
            return (
                f"Review approved: the tool result '{tool_result}' "
                f"answers '{query}' and is consistent with the "
                "research and retrieved context."
            )

        return (
            f"Review approved: the research answers '{query}' from "
            "the retrieved context with no contradictions."
        )

    def _answer(self, text: str) -> str:
        query = _section(text, "Query:")
        tool_result = _section(text, "Tool result:")
        research = _section(text, "Research:")

        if tool_result:
            decision = decide_tool(query)
            if decision and decision["tool"] == "calculator":
                expression = decision["input"]["expression"]
                return (
                    f"The result of {expression} is {tool_result}."
                )
            if decision and decision["tool"] == "get_system_status":
                return f"System status: {tool_result}."
            return tool_result

        return research
