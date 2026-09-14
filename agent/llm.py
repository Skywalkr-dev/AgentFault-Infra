from langchain_core.messages import AIMessage


class MockLLM:
    def invoke(self, prompt):
        if isinstance(prompt, list):
            prompt = prompt[-1].content

        if "You are the researcher sub-agent" in prompt:
            if "847 * 293" in prompt and "Previous tool result:" in prompt:
                if "Previous tool result:\n" in prompt:
                    tool_result = prompt.split("Previous tool result:\n", 1)[1].strip()

                    if tool_result:
                        return AIMessage(
                            content=f"The calculator returned: {tool_result}"
                        )

            return AIMessage(
                content='{"tool": "calculator", "input": {"expression": "847 * 293"}}'
            )

        if "You are the reviewer sub-agent" in prompt:
            return AIMessage(
                content="The research and tool result are correct."
            )

        if "Produce the final answer" in prompt:
            return AIMessage(
                content="The product of 847 and 293 is 248171."
            )

        return AIMessage(content="Mock response")
