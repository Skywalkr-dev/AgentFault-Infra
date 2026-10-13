"""End-to-end pipeline test.

Exercises every subsystem in one flow: record a baseline trajectory, inject a
fault, replay the pair with the deterministic engine, serve the result through
the dashboard API, consume it through the replay worker, and export it as a
verifiable dataset release.
"""

import json
from dataclasses import asdict
from pathlib import Path

from agent.graph import build_graph, set_llm
from agent.mock_llm import MockLLM
from injector.compatibility import compatible_faults
from injector.faults import Fault, FaultType
from injector.generator import DatasetGenerator
from injector.injector import FaultInjector
from injector.real_trajectory import events_to_record, load_events
from replay import ReplayConfig, ReplayEngine
from scripts.export_dataset import export_dataset
from scripts.verify_export import verify_export
from trajectory.events import TrajectoryRecorder
from worker.worker import ReplayWorker


def write_graph_baseline(tmp_path, query="Compute 2 + 3.", trajectory_id="traj_e2e"):
    """Record a real, deterministic baseline via the agent graph."""

    set_llm(MockLLM())
    recorder = TrajectoryRecorder(trajectory_id)
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

    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    path = baseline_dir / f"{trajectory_id}.jsonl"

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(recorder.to_jsonl())
        handle.write("\n")

    return baseline_dir, trajectory_id


def inject_candidates(record, tmp_path):
    """Yield every injectable (fault_type, injected_record) for the baseline."""

    generator = DatasetGenerator(
        baseline_dir=str(tmp_path / "gen_baseline"),
        output_dir=str(tmp_path / "gen_injected"),
        seed=42,
    )
    injector = FaultInjector()

    for fault_type, step_indices in compatible_faults(record).items():
        if fault_type == FaultType.PLAN_INVALID_DEPENDENCY:
            continue

        for step_index in step_indices:
            params = generator.build_parameters(fault_type, record, step_index)

            if params is None:
                continue

            yield injector.inject(
                record,
                Fault(
                    fault_type=fault_type,
                    step=step_index,
                    parameters=params,
                    seed=42,
                ),
            )


def inject_visible_fault(record, tmp_path, engine):
    """Pick the first injection that measurably lowers the success score."""

    for injected in inject_candidates(record, tmp_path):
        if engine.compare(record, injected).success_delta > 0:
            return injected

    raise AssertionError("no injection produced a positive success delta")


def persist(tmp_path, baseline_record, injected_record):
    baseline_dir = tmp_path / "baseline"
    injected_dir = tmp_path / "injected"
    baseline_dir.mkdir(parents=True, exist_ok=True)
    injected_dir.mkdir(parents=True, exist_ok=True)

    baseline_event_path = baseline_dir / f"{baseline_record.trajectory_id}.jsonl"

    if not baseline_event_path.is_file():
        raise AssertionError("baseline event log was not written by fixture")

    (injected_dir / f"{injected_record.trajectory_id}.json").write_text(
        json.dumps(asdict(injected_record)), encoding="utf-8"
    )

    return baseline_dir, injected_dir


def write_replay_payload(tmp_path, engine, baseline, injected):
    comparison = engine.compare(baseline, injected)
    results = [comparison.to_dict()]

    by_fault: dict = {}
    for result in results:
        fault = result["fault_type"] or "UNKNOWN"
        entry = by_fault.setdefault(fault, {"count": 0, "delta": 0.0})
        entry["count"] += 1
        entry["delta"] += result["success_delta"]

    for entry in by_fault.values():
        entry["mean_delta"] = round(entry["delta"] / entry["count"], 4)

    payload = {
        "config": engine.config.to_dict(),
        "summary": {
            "count": 1,
            "mean_success_delta": comparison.success_delta,
            "deterministic_baselines": 1 if comparison.baseline_replay_deterministic else 0,
            "by_fault": by_fault,
        },
        "results": results,
    }

    replay_dir = tmp_path / "replay"
    replay_dir.mkdir(parents=True, exist_ok=True)
    replay_path = replay_dir / "replay.json"
    replay_path.write_text(json.dumps(payload), encoding="utf-8")

    return comparison, replay_path


def test_full_pipeline_end_to_end(tmp_path):
    from fastapi.testclient import TestClient

    from dashboard import DatasetStore, create_app

    baseline_dir, baseline_id = write_graph_baseline(tmp_path)
    baseline = events_to_record(
        load_events(baseline_dir / f"{baseline_id}.jsonl")
    )

    config = ReplayConfig.from_env()
    engine = ReplayEngine(config)

    injected = inject_visible_fault(baseline, tmp_path, engine)

    assert injected.fault_injected is True
    assert injected.origin_step is not None
    assert sum(1 for step in injected.steps if step.is_root_cause) == 1

    baseline_dir, injected_dir = persist(tmp_path, baseline, injected)

    comparison, replay_path = write_replay_payload(
        tmp_path, engine, baseline, injected
    )

    assert comparison.success_delta > 0
    assert comparison.baseline_replay_deterministic is True
    assert comparison.propagation["origin_step"] == injected.origin_step

    store = DatasetStore(
        baseline_dir=baseline_dir,
        injected_dir=injected_dir,
        replay_path=replay_path,
    )
    app = create_app(store)

    with TestClient(app) as client:
        meta = client.get("/api/meta").json()
        detail = client.get(
            f"/api/trajectories/{injected.trajectory_id}"
        ).json()
        one = client.get(
            f"/api/replay/{injected.trajectory_id}"
        ).json()
        chain = client.get(
            f"/api/propagation/{injected.trajectory_id}"
        ).json()

    assert meta["counts"] == {"baseline": 1, "injected": 1, "replay": 1}
    assert detail["record"]["fault_type"] == injected.fault_type
    assert one["success_delta"] == comparison.success_delta
    assert chain["origin_step"] == injected.origin_step

    worker = ReplayWorker(
        baseline_dir=baseline_dir, injected_dir=injected_dir, config=config
    )
    status = worker.status()

    assert status["eligible"] == 1
    assert status["processed"] == 0

    completed = worker.process(1)

    assert len(completed) == 1
    assert completed[0]["injected_id"] == injected.trajectory_id
    assert worker.status()["processed"] == 1
    assert worker.status()["queue_depth"] == 0
    assert worker.mean_delta == comparison.success_delta

    out_dir = tmp_path / "release"
    manifest = export_dataset(
        baseline_dir=baseline_dir,
        injected_dir=injected_dir,
        replay_path=replay_path,
        out_dir=out_dir,
        created_at="2026-10-13T00:00:00+00:00",
    )

    assert manifest["counts"]["baseline"] == 1
    assert manifest["counts"]["injected"] == 1
    assert manifest["counts"]["replay"] == 1
    assert injected.fault_type in manifest["fault_counts"]
    assert verify_export(out_dir) == []


def test_full_pipeline_is_deterministic(tmp_path):
    """Two independent runs of the whole flow produce identical comparisons."""

    baseline_dir, baseline_id = write_graph_baseline(tmp_path)
    baseline = events_to_record(
        load_events(baseline_dir / f"{baseline_id}.jsonl")
    )

    engine = ReplayEngine(ReplayConfig.from_env())
    injected = inject_visible_fault(baseline, tmp_path, engine)

    first = engine.compare(baseline, injected).to_dict()
    second = engine.compare(baseline, injected).to_dict()

    assert first == second
    assert first["success_delta"] == second["success_delta"]
    assert first["propagation"] == second["propagation"]


def test_real_dataset_full_stack_smoke():
    import pytest

    if not Path("data/trajectories/injected").is_dir():
        pytest.skip("dataset not present")

    from dashboard import DatasetStore
    from replay.records import load_baselines, load_injected

    baselines = load_baselines("data/trajectories/baseline")
    injected = load_injected("data/trajectories/injected")

    assert len(baselines) == 160
    assert len(injected) == 500

    engine = ReplayEngine(ReplayConfig.from_env())
    sample_id = sorted(injected)[0]
    injected_record = injected[sample_id]
    baseline_record = baselines[sample_id.split("_fault_")[0]]

    comparison = engine.compare(baseline_record, injected_record)

    assert comparison.baseline_replay_deterministic is True

    store = DatasetStore()
    assert store.meta()["counts"] == {
        "baseline": 160,
        "injected": 500,
        "replay": 500,
    }
    assert store.get_replay(sample_id) is not None
