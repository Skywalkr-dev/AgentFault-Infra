from dataclasses import asdict

from agent.graph import build_graph, set_llm
from agent.mock_llm import MockLLM
from injector.compatibility import compatible_faults
from injector.faults import Fault, FaultType
from injector.generator import DatasetGenerator
from injector.injector import FaultInjector
from injector.real_trajectory import events_to_record
from scripts.validate_dataset import validate_record
from trajectory.events import TrajectoryRecorder


def build_record(query="Check the worker service status."):
    set_llm(MockLLM())
    recorder = TrajectoryRecorder("traj_pipe")
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


def test_graph_pipeline_is_deterministic():
    first = build_record()
    second = build_record()

    assert [s.step_type for s in first.steps] == [
        s.step_type for s in second.steps
    ]
    assert [s.input for s in first.steps] == [
        s.input for s in second.steps
    ]
    assert [s.output for s in first.steps] == [
        s.output for s in second.steps
    ]


def test_every_compatible_fault_produces_a_valid_record(tmp_path):
    record = build_record()
    generator = DatasetGenerator(
        baseline_dir=str(tmp_path / "baseline"),
        output_dir=str(tmp_path / "injected"),
        seed=7,
    )
    injector = FaultInjector()

    covered = set()
    faults = compatible_faults(record)

    assert faults, "no compatible faults found for the baseline record"
    assert FaultType.PLAN_INVALID_DEPENDENCY not in faults

    for fault_type, step_indices in faults.items():
        for step_index in step_indices:
            params = generator.build_parameters(
                fault_type, record, step_index
            )

            if params is None:
                continue

            injected = injector.inject(
                record,
                Fault(
                    fault_type=fault_type,
                    step=step_index,
                    parameters=params,
                    seed=11,
                ),
            )

            assert injected.fault_injected is True
            assert injected.source == "INJECTED"
            assert injected.origin_step == step_index
            assert injected.outcome.status == "FAIL"
            assert sum(
                1 for step in injected.steps if step.is_root_cause
            ) == 1

            errors = validate_record(asdict(injected))
            assert errors == [], (fault_type, step_index, errors)

            covered.add(fault_type.value)

    assert len(covered) >= 15
