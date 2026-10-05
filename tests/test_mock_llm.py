import json

import pytest

from agent.graph import build_graph, set_llm
from agent.llm import active_config, make_llm
from agent.mock_llm import (
    MOCK_CONFIG,
    MockLLM,
    decide_tool,
    extract_expression,
    grounded_answer,
)
from trajectory.events import TrajectoryRecorder


def _researcher_prompt(query, tool_result="", context="AgentFault context."):
    return (
        "You are the researcher sub-agent.\n\n"
        "Answer the user's query.\n\n"
        "If a tool is required, respond ONLY with JSON.\n\n"
        f"User query:\n{query}\n\n"
        f"Retrieved context:\n{context}\n\n"
        f"Previous tool result:\n{tool_result}\n"
    )


def _reviewer_prompt(query, research, tool_result=""):
    return (
        "You are the reviewer sub-agent.\n\n"
        "Review the research and tool result for correctness.\n\n"
        f"User query:\n{query}\n\n"
        f"Research:\n{research}\n\n"
        f"Tool result:\n{tool_result}\n\n"
        "Retrieved context:\nsome context\n"
    )


def _answer_prompt(query, research, tool_result="", review=""):
    return (
        "Produce the final answer to the user's query.\n\n"
        f"Query:\n{query}\n\n"
        f"Research:\n{research}\n\n"
        f"Tool result:\n{tool_result}\n\n"
        f"Review:\n{review}\n"
    )


def test_config_is_temperature_zero():
    assert MOCK_CONFIG.temperature == 0.0
    assert MockLLM().config.temperature == 0.0
    assert active_config("mock").temperature == 0.0
    assert active_config().model == "mock-llm-v1"
    assert active_config().provider == "mock"
    assert isinstance(make_llm("mock"), MockLLM)


def test_unknown_provider_rejected():
    with pytest.raises(ValueError):
        make_llm("gpt")


def test_researcher_responses_are_deterministic():
    llm = MockLLM()
    prompt = _researcher_prompt("What is 847 * 293?")
    assert llm.invoke(prompt).content == llm.invoke(prompt).content


def test_calculator_request_uses_json_protocol():
    content = MockLLM().invoke(
        _researcher_prompt("What is 847 * 293?")
    ).content
    data = json.loads(content)
    assert data["tool"] == "calculator"
    assert data["input"]["expression"] == "847 * 293"


def test_status_request_uses_json_protocol():
    content = MockLLM().invoke(
        _researcher_prompt("Check the worker service status.")
    ).content
    data = json.loads(content)
    assert data["tool"] == "get_system_status"
    assert data["input"]["service"] == "worker"


def test_expression_extraction_handles_worded_math():
    assert extract_expression("What is 9876 divided by 12?") == "9876 / 12"
    assert extract_expression("What is 73 squared?") == "73 ** 2"
    assert extract_expression("Calculate 9999 - 4321.") == "9999 - 4321"
    assert extract_expression("Compute 12 * 8.") == "12 * 8"
    assert extract_expression("What is AgentFault?") is None


def test_decide_tool_defaults_status_service():
    decision = decide_tool("What is the current system status?")
    assert decision["tool"] == "get_system_status"
    assert decision["input"]["service"] == "api"
    assert decide_tool("What is AgentFault?") is None


def test_knowledge_answer_is_plain_grounded_text():
    prompt = _researcher_prompt(
        "What is AgentFault?",
        context=(
            "AgentFault is a framework for evaluating the reliability "
            "of AI agents. AgentFault-500 is a dataset containing "
            "clean and fault-injected agent trajectories."
        ),
    )
    content = MockLLM().invoke(prompt).content
    with pytest.raises(json.JSONDecodeError):
        json.loads(content)
    assert "framework" in content


def test_grounded_answer_prefers_keyword_overlap():
    context = "Cats sleep a lot. AgentFault is a reliability framework."
    answer = grounded_answer("What is AgentFault?", context)
    assert answer.startswith("AgentFault")


def test_tool_followup_is_plain_text():
    content = MockLLM().invoke(
        _researcher_prompt("What is 21 * 2?", tool_result="42")
    ).content
    with pytest.raises(json.JSONDecodeError):
        json.loads(content)
    assert "42" in content


def test_reviewer_and_answer_are_deterministic():
    llm = MockLLM()
    review_prompt = _reviewer_prompt(
        "What is 2 + 2?", "the answer is 4", "4"
    )
    answer_prompt = _answer_prompt(
        "What is 2 + 2?",
        "the answer is 4",
        tool_result="4",
        review="approved",
    )
    assert llm.invoke(review_prompt).content == llm.invoke(
        review_prompt
    ).content
    review = llm.invoke(review_prompt).content
    assert "approved" in review.lower()

    answer = llm.invoke(answer_prompt).content
    assert "4" in answer
    assert answer == llm.invoke(answer_prompt).content


def test_graph_run_is_deterministic_and_records_handoffs():
    set_llm(MockLLM())
    graph = build_graph()

    def run():
        recorder = TrajectoryRecorder("traj_test")
        recorder.record(
            "trajectory_start",
            input={"query": "What is 847 * 293?"},
        )
        result = graph.invoke(
            {
                "query": "What is 847 * 293?",
                "retrieved_context": "",
                "tool_result": "",
                "research": "",
                "review": "",
                "answer": "",
                "recorder": recorder,
            }
        )
        recorder.record("trajectory_end", output=result["answer"])
        events = [
            (e.event_type, e.agent, e.input, e.output, e.tool, e.status)
            for e in recorder.events
        ]
        return result["answer"], events

    answer_a, events_a = run()
    answer_b, events_b = run()

    assert answer_a == answer_b
    assert events_a == events_b

    types = [event[0] for event in events_a]
    assert types == [
        "trajectory_start",
        "retrieval",
        "llm_call",
        "tool_call",
        "tool_result",
        "llm_call",
        "handoff",
        "llm_call",
        "handoff",
        "llm_call",
        "trajectory_end",
    ]

    handoffs = [event for event in events_a if event[0] == "handoff"]
    assert len(handoffs) == 2
    assert handoffs[0][1] == "reviewer"
    assert handoffs[1][1] == "answer"

    expected = 847 * 293
    assert answer_a == f"The result of 847 * 293 is {expected}."
