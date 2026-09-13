import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END

from .state import AgentState
from .retrieval import retrieve


load_dotenv()


llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    temperature=0,
    api_key=os.environ["GEMINI_API_KEY"],
)


def retrieve_node(state: AgentState):
    context = retrieve(state["query"])

    return {
        "retrieved_context": context
    }


def researcher_node(state: AgentState):
    prompt = f"""
You are the researcher sub-agent.

Answer the user's query using the retrieved context below.

Query:
{state["query"]}

Retrieved context:
{state["retrieved_context"]}
"""

    response = llm.invoke(prompt)

    return {
        "research": response.content
    }


def reviewer_node(state: AgentState):
    prompt = f"""
You are the reviewer sub-agent.

Review the research below for correctness and relevance.
Identify anything missing, incorrect, or unsupported by the retrieved context.

User query:
{state["query"]}

Research:
{state["research"]}

Retrieved context:
{state["retrieved_context"]}
"""

    response = llm.invoke(prompt)

    return {
        "review": response.content
    }


def answer_node(state: AgentState):
    prompt = f"""
Produce the final answer to the user's query.

Use the research and review below.

Query:
{state["query"]}

Research:
{state["research"]}

Review:
{state["review"]}
"""

    response = llm.invoke(prompt)

    return {
        "answer": response.content
    }


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("retrieval", retrieve_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("answer", answer_node)

    graph.add_edge(START, "retrieval")
    graph.add_edge("retrieval", "researcher")
    graph.add_edge("researcher", "reviewer")
    graph.add_edge("reviewer", "answer")
    graph.add_edge("answer", END)

    return graph.compile()
