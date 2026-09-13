from langgraph.graph import StateGraph, START, END

from .state import AgentState
from .retrieval import retrieve


def retrieve_node(state: AgentState):
    return {
        "retrieved_context": retrieve(state["query"])
    }


def research_node(state: AgentState):
    context = state["retrieved_context"]

    return {
        "research": (
            f"Based on the retrieved knowledge:\n\n{context}"
        )
    }


def review_node(state: AgentState):
    return {
        "review": "Research reviewed successfully."
    }


def answer_node(state: AgentState):
    return {
        "answer": (
            f"Query: {state['query']}\n\n"
            f"{state['research']}\n\n"
            f"Review: {state['review']}"
        )
    }


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("retrieval", retrieve_node)
    graph.add_node("researcher", research_node)
    graph.add_node("reviewer", review_node)
    graph.add_node("answer", answer_node)

    graph.add_edge(START, "retrieval")
    graph.add_edge("retrieval", "researcher")
    graph.add_edge("researcher", "reviewer")
    graph.add_edge("reviewer", "answer")
    graph.add_edge("answer", END)

    return graph.compile()
