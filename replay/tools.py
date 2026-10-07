from dataclasses import dataclass
from typing import Any

from agent.tools import calculator, get_system_status

KNOWN_TOOLS = {
    "calculator": calculator,
    "get_system_status": get_system_status,
}


def next_tool_result(steps, position: int):
    for step in steps[position + 1:]:
        if step.step_type == "TOOL_CALL":
            return None
        if step.step_type == "TOOL_RESULT":
            return step
    return None


@dataclass
class ToolCallTrace:
    step: int
    tool: str | None
    input: Any
    mocked: bool
    mocked_output: str
    recorded_output: str | None
    matched: bool
    error: bool

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "tool": self.tool,
            "input": self.input,
            "mocked": self.mocked,
            "mocked_output": self.mocked_output,
            "recorded_output": self.recorded_output,
            "matched": self.matched,
            "error": self.error,
        }


def execute_tool(tool_name: str | None, tool_input: Any) -> str:
    """Run a tool in the mocked registry, never touching real side effects."""
    tool = KNOWN_TOOLS.get(tool_name)

    if tool is None:
        return f"Unknown tool: {tool_name}"

    if not isinstance(tool_input, dict):
        return f"Tool error: invalid input {tool_input!r}"

    try:
        return str(tool.invoke(tool_input))
    except Exception as exc:
        return f"Tool error: {exc}"


class MockToolRegistry:
    def __init__(self, tools: dict | None = None):
        self.tools = dict(tools or KNOWN_TOOLS)

    def known(self, tool_name: str | None) -> bool:
        return tool_name in self.tools

    def invoke(self, tool_name: str | None, tool_input: Any) -> str:
        tool = self.tools.get(tool_name)

        if tool is None:
            return f"Unknown tool: {tool_name}"

        if not isinstance(tool_input, dict):
            return f"Tool error: invalid input {tool_input!r}"

        try:
            return str(tool.invoke(tool_input))
        except Exception as exc:
            return f"Tool error: {exc}"

    def trace(self, step, steps, position: int) -> ToolCallTrace:
        recorded_step = next_tool_result(steps, position)
        recorded = (
            str(recorded_step.output)
            if recorded_step is not None
            else None
        )
        mocked = self.invoke(step.tool_name, step.input)
        error = mocked.startswith("Unknown tool:") or mocked.startswith(
            "Tool error:"
        ) or mocked.startswith("Calculation error:")

        return ToolCallTrace(
            step=step.step_index,
            tool=step.tool_name,
            input=step.input,
            mocked=True,
            mocked_output=mocked,
            recorded_output=recorded,
            matched=recorded is not None and mocked == recorded,
            error=error,
        )
