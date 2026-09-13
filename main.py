from agent.graph import build_graph

graph = build_graph()

result = graph.invoke({
    "query": "What is 847 * 293?",
    "retrieved_context": "",
    "tool_result": "",
    "research": "",
    "review": "",
    "answer": "",
})

print(result["answer"])
