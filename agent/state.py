from typing import TypedDict
from langchain_core.messages import AnyMessage


class AgentState(TypedDict):
    query: str
    messages: list[AnyMessage]
    retrieved_context: str
    research: str
    review: str
    answer: str
