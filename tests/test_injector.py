from agent.graph import build_graph, set_llm
from agent.mock_llm import MockLLM
from injector.faults import Fault, FaultType
from injector.injector import FaultInjector
from injector.real_trajectory import events_to_record
from trajectory.events import TrajectoryRecorder

QUERY = "What is 847 * 293?"

EXPECTED_STEP_TYPES = [
    "RETRIEVAL",
    "LLM_CALL",
    "TOOL_CALL",
    "TOOL_RESULT",
    "LLM_CALL",
    "HANDOFF",
    "LLM_CALL",
    "HANDOFF",
    "LLM_CALL",
]


def build_record(query=QUERY):
    set_llm(MockLLM())
    recorder = TrajectoryRecorder("traj_test")
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


def test_record_has_expected_shape():
    record = build_record()

    assert record.agent_config.model == "mock-llm-v1"
    assert record.agent_config.temperature == 0.0
    assert record.num_steps == len(EXPECTED_STEP_TYPES)
    assert [step.step_type for step in record.steps] == EXPECTED_STEP_TYPES
    assert [step.step_index for step in record.steps] == list(
        range(1, len(EXPECTED_STEP_TYPES) + 1)
    )
    assert record.fault_injected is False


def test_tool_wrong_tool_injection_contract():
    record = build_record()
    tool_step = next(
        step for step in record.steps if step.step_type == "TOOL_CALL"
    )

    fault = Fault(
        fault_type=FaultType.TOOL_WRONG_TOOL,
        step=tool_step.step_index,
        parameters={"injected_tool": "wrong_tool"},
        seed=42,
    )

    injected = FaultInjector().inject(record, fault)

    assert injected.trajectory_id == (
        f"traj_test_fault_TOOL_WRONG_TOOL_step_{tool_step.step_index}"
    )
    assert injected.fault_injected is True
    assert injected.fault_type == "TOOL_WRONG_TOOL"
    assert injected.origin_step == tool_step.step_index
    assert injected.source == "INJECTED"

    root = next(step for step in injected.steps if step.is_root_cause)
    assert root.step_index == tool_step.step_index
    assert root.tool_name == "wrong_tool"

    assert injected.injection_params["operator"] == "REPLACE_TOOL"
    assert injected.injection_params["original_tool"] == "calculator"
    assert injected.injection_params["injected_tool"] == "wrong_tool"
    assert injected.injection_params["random_seed"] == 42

    assert injected.outcome.status == "FAIL"
    assert injected.outcome.success_score == 0.0


def test_injection_does_not_mutate_the_original():
    record = build_record()
    original_tools = [step.tool_name for step in record.steps]

    tool_step = next(
        step for step in record.steps if step.step_type == "TOOL_CALL"
    )

    FaultInjector().inject(
        record,
        Fault(
            fault_type=FaultType.TOOL_WRONG_TOOL,
            step=tool_step.step_index,
            parameters={"injected_tool": "wrong_tool"},
            seed=1,
        ),
    )

    assert record.fault_injected is False
    assert [step.tool_name for step in record.steps] == original_tools
