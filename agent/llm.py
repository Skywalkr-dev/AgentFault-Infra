from langchain_core.messages import AIMessage


class MockLLM:
    def invoke(self, prompt):
        if isinstance(prompt, list):
            prompt = prompt[-1].content

        if "You are the researcher sub-agent" in prompt:
            return self._researcher(prompt)

        if "You are the reviewer sub-agent" in prompt:
            return AIMessage(
                content="The research and tool result are consistent with the query."
            )

        if "Produce the final answer" in prompt:
            return self._answer(prompt)

        return AIMessage(content="Mock response")

    def _researcher(self, prompt):
        query = self._extract(prompt, "User query:", "Retrieved context:")
        previous = self._extract(prompt, "Previous tool result:", None)

        if previous.strip():
            return AIMessage(
                content=f"The tool returned: {previous.strip()}"
            )

        query_lower = query.lower()

        if any(op in query_lower for op in ["+", "-", "*", "/", "calculate", "multiply", "add", "subtract", "divide"]):
            expression = self._extract_expression(query)

            return AIMessage(
                content=(
                    '{"tool": "calculator", '
                    f'"input": {{"expression": "{expression}"}}' 
                    '}'
                )
            )

        if "status" in query_lower or "health" in query_lower:
            service = "api"

            for candidate in ["api", "worker", "database"]:
                if candidate in query_lower:
                    service = candidate
                    break

            return AIMessage(
                content=(
                    '{"tool": "get_system_status", '
                    f'"input": {{"service": "{service}"}}'
                    '}'
                )
            )

        return AIMessage(
            content=f"Based on the retrieved context, the answer concerns: {query}"
        )

    def _answer(self, prompt):
        query = self._extract(prompt, "Query:", "Research:")
        research = self._extract(prompt, "Research:", "Tool result:")
        tool_result = self._extract(prompt, "Tool result:", "Review:")

        if tool_result.strip():
            answer = f"For the query '{query}', the tool result is {tool_result.strip()}."
        elif research.strip():
            answer = research.strip()
        else:
            answer = f"The answer to '{query}' is based on the available context."

        return AIMessage(content=answer)

    @staticmethod
    def _extract(text, start, end):
        if start not in text:
            return ""

        value = text.split(start, 1)[1]

        if end and end in value:
            value = value.split(end, 1)[0]

        return value.strip()

    @staticmethod
    def _extract_expression(query):
        replacements = {
            "calculate": "",
            "what is": "",
            "multiply": "*",
            "times": "*",
            "plus": "+",
            "add": "+",
            "minus": "-",
            "subtract": "-",
            "divided by": "/",
            "divide": "/",
        }

        expression = query.lower()

        for old, new in replacements.items():
            expression = expression.replace(old, new)

        return expression.strip(" ?.")
