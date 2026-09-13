import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from .state import AgentState
from .retrieval import retrieve
from .tools import calculator, get_system_status


load_dotenv()

tools = [
    calculator,
    get_system_status,
]

llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    api_key=os.environ["GEMINI_API_KEY"],
)

llm_with_tools = llm.bind_tools(tools)


def retrieve_node(state: AgentState):
    return {
        "retrieved_context": retrieve(state["query"])
    }


def researcher_node(state: AgentState):
    prompt = f"""
You are the researcher sub-agent.

Use the available tools when useful.

User query:
{state["query"]}

Retrieved context:
{state["retrieved_context"]}
"""

    messages = [
        HumanMessage(content=prompt)
    ]

    response = llm_with_tools.invoke(messages)

    return {
        "messages": messages + [response],
        "research": response.content,
    }


def reviewer_node(state: AgentState):
    prompt = f"""
You are the reviewer sub-agent.

Review the research for correctness and relevance.

User query:
{state["query"]}

Research:
{state["research"]}
"""

    response = llm.invoke(prompt)

    return {
        "review": response.content
    }


def answer_node(state: AgentState):
    prompt = f"""
Produce the final answer to the user's query.

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
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("answer", answer_node)

    graph.add_edge(START, "retrieval")
    graph.add_edge("retrieval", "researcher")
    graph.add_edge("researcher", "tools")
    graph.add_edge("tools", "reviewer")
    graph.add_edge("reviewer", "answer")
    graph.add_edge("answer", END)

    return graph.compile()
