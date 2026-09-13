from typing import TypedDict


class AgentState(TypedDict):
    query: str
    retrieved_context: str
    tool_result: str
    research: str
    review: str
    answer: str
