import copy

from agent.graph import build_graph, set_llm
from agent.mock_llm import MockLLM
from injector.real_trajectory import events_to_record
from injector.schema import Outcome
from replay import (
    MockToolRegistry,
    ReplayConfig,
    ReplayEngine,
    evaluate,
)
from trajectory.events import TrajectoryRecorder


def build_record(query="Compute 12 + 30."):
    set_llm(MockLLM())
    recorder = TrajectoryRecorder("traj_replay")

    recorder.record(
        "trajectory_start",
        input={"query": query},
        metadata={
            "framework": "LangGraph",
            "provider": "mock",
            "model": "mock-llm-v1",
            "temperature": 0.0,
        },
    )

    graph = build_graph()
    result = graph.invoke(
        {
            "query": query,
            "retrieved_context": "",
            "tool_result": "",
            "research": "",
            "review": "",
            "answer": "",
            "recorder": recorder,
        }
    )
    recorder.record("trajectory_end", output=result["answer"])

    return events_to_record(recorder.events)


def corrupt_tool_call(record):
    injected = copy.deepcopy(record)

    for step in injected.steps:
        if step.step_type == "TOOL_CALL":
            step.input = {"expression": "invalid_162"}
            injected.fault_type = "TOOL_WRONG_ARGUMENT"
            injected.origin_step = step.step_index
            injected.fault_injected = True
            break

    injected.outcome = Outcome(status="FAIL", success_score=0.0)
    injected.trajectory_id = record.trajectory_id + "_fault"

    return injected


def test_replay_config_is_deterministic():
    config = ReplayConfig.from_env()

    assert config.provider == "mock"
    assert config.model == "mock-llm-v1"
    assert config.temperature == 0.0
    assert config.mock_tools is True


def test_baseline_replay_is_deterministic():
    record = build_record()
    engine = ReplayEngine()
    first = engine.replay(record)
    second = engine.replay(record)

    assert first.deterministic is True
    assert first.matched_steps == first.total_steps
    assert first.to_dict()["steps"] == second.to_dict()["steps"]


def test_mocked_tool_registry_is_used():
    record = build_record()
    engine = ReplayEngine()
    result = engine.replay(record)

    assert result.tool_calls, "expected at least one mocked tool call"
    assert all(call.mocked for call in result.tool_calls)
    assert all(call.matched for call in result.tool_calls)
    assert MockToolRegistry().invoke("nonexistent_tool", {}) == (
        "Unknown tool: nonexistent_tool"
    )


def test_baseline_scores_full_marks():
    record = build_record()
    report = evaluate(record)

    assert report.score == 1.0
    assert report.failed_checks == []


def test_injected_record_scores_lower_and_delta_positive():
    baseline = build_record()
    injected = corrupt_tool_call(baseline)

    baseline_report = evaluate(baseline)
    injected_report = evaluate(injected)

    assert injected_report.score < baseline_report.score

    comparison = ReplayEngine().compare(baseline, injected)

    assert comparison.success_delta > 0
    assert comparison.baseline_score == 1.0
    assert comparison.injected_score < 1.0
    assert comparison.baseline_replay_deterministic is True


def test_propagation_chain_traces_the_fault():
    baseline = build_record()
    injected = corrupt_tool_call(baseline)

    comparison = ReplayEngine().compare(baseline, injected)
    propagation = comparison.propagation

    assert propagation["fault_type"] == "TOOL_WRONG_ARGUMENT"
    assert propagation["origin_step"] == injected.origin_step
    assert propagation["affected_steps"]
    assert propagation["chain"]
    assert isinstance(propagation["edges"], list)

    affected = {node["step_index"] for node in propagation["chain"]}
    assert injected.origin_step in affected

    origin = next(
        node
        for node in propagation["nodes"]
        if node["step_index"] == injected.origin_step
    )
    assert origin["is_origin"] is True
    assert origin["status"] == "changed"
    assert any(
        change["field"] == "input" for change in origin["changes"]
    )


def test_propagation_edges_connect_a_cascade():
    baseline = build_record()
    injected = copy.deepcopy(baseline)
    injected.trajectory_id = baseline.trajectory_id + "_cascade"

    changed = []

    for step in injected.steps:
        if step.step_type in ("TOOL_CALL", "TOOL_RESULT"):
            if step.step_type == "TOOL_CALL":
                step.input = {"expression": "invalid_162"}
            else:
                step.output = "0"
            changed.append(step.step_index)

    assert len(changed) == 2

    comparison = ReplayEngine().compare(baseline, injected)
    edges = comparison.propagation["edges"]

    assert edges == [[changed[0], changed[1]]]
