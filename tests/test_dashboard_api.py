import json
from pathlib import Path

from dashboard import DatasetStore, create_app
from trajectory.events import TrajectoryEvent, now


def write_baseline(tmp_path, trajectory_id="traj_b1"):
    baseline_dir = tmp_path / "baseline"
    baseline_dir.mkdir(parents=True, exist_ok=True)

    events = [
        TrajectoryEvent(
            trajectory_id, now(), "trajectory_start", 0,
            input={"query": "Compute 2 + 3."},
            metadata={
                "framework": "LangGraph",
                "model": "mock-llm-v1",
                "temperature": 0.0,
            },
        ),
        TrajectoryEvent(
            trajectory_id, now(), "retrieval", 1,
            agent="retrieval",
            input="Compute 2 + 3.",
            output="AgentFault knowledge.",
        ),
        TrajectoryEvent(
            trajectory_id, now(), "llm_call", 2,
            agent="researcher",
            input="research prompt",
            output='{"tool": "calculator", "input": {"expression": "2 + 3"}}',
        ),
        TrajectoryEvent(
            trajectory_id, now(), "tool_call", 3,
            agent="researcher",
            tool="calculator",
            input={"expression": "2 + 3"},
        ),
        TrajectoryEvent(
            trajectory_id, now(), "tool_result", 4,
            agent="researcher",
            tool="calculator",
            output="5",
        ),
        TrajectoryEvent(
            trajectory_id, now(), "handoff", 5,
            agent="reviewer",
            input={
                "task": "Compute 2 + 3.",
                "from": "researcher",
                "to": "reviewer",
            },
            output="Findings.",
            metadata={
                "from": "researcher",
                "to": "reviewer",
                "responsibility": "verify_research",
                "role": "reviewer",
            },
        ),
        TrajectoryEvent(
            trajectory_id, now(), "llm_call", 6,
            agent="reviewer",
            input="review prompt",
            output="Review approved.",
        ),
        TrajectoryEvent(
            trajectory_id, now(), "handoff", 7,
            agent="answer",
            input={
                "task": "Compute 2 + 3.",
                "from": "reviewer",
                "to": "answer",
            },
            output="Review approved.",
            metadata={
                "from": "reviewer",
                "to": "answer",
                "responsibility": "compose_final_answer",
                "role": "answer",
            },
        ),
        TrajectoryEvent(
            trajectory_id, now(), "llm_call", 8,
            agent="answer",
            input="answer prompt",
            output="The result of 2 + 3 is 5.",
        ),
        TrajectoryEvent(
            trajectory_id, now(), "trajectory_end", 9,
            output="The result of 2 + 3 is 5.",
        ),
    ]

    path = baseline_dir / f"{trajectory_id}.jsonl"
    path.write_text(
        "\n".join(event.to_json() for event in events) + "\n",
        encoding="utf-8",
    )

    return baseline_dir, trajectory_id


def write_injected(tmp_path, baseline_id="traj_b1"):
    injected_dir = tmp_path / "injected"
    injected_dir.mkdir(parents=True, exist_ok=True)

    injected_id = f"{baseline_id}_fault_TOOL_WRONG_ARGUMENT_step_3"

    steps = [
        {"step_index": 1, "step_type": "RETRIEVAL", "agent_id": "retrieval",
         "input": "Compute 2 + 3.", "output": "AgentFault knowledge."},
        {"step_index": 2, "step_type": "LLM_CALL", "agent_id": "researcher",
         "input": "research prompt",
         "output": '{"tool": "calculator", "input": {"expression": "2 + 3"}}'},
        {"step_index": 3, "step_type": "TOOL_CALL", "agent_id": "researcher",
         "tool_name": "calculator",
         "input": {"expression": "invalid_2"}, "output": None},
        {"step_index": 4, "step_type": "TOOL_RESULT", "agent_id": "researcher",
         "tool_name": "calculator", "input": None, "output": "0"},
        {"step_index": 5, "step_type": "LLM_CALL", "agent_id": "reviewer",
         "input": "review prompt", "output": "Review approved."},
        {"step_index": 6, "step_type": "HANDOFF", "agent_id": "answer",
         "input": {"task": "Compute 2 + 3.", "from": "reviewer", "to": "answer"},
         "output": "Review approved.",
         "metadata": {"responsibility": "compose_final_answer", "role": "answer"}},
        {"step_index": 7, "step_type": "LLM_CALL", "agent_id": "answer",
         "input": "answer prompt", "output": "The result of 2 + 3 is 0."},
    ]

    step_defaults = {
        "retrieved_docs": None,
        "is_root_cause": False,
        "status": "success",
        "metadata": {},
        "tool_name": None,
    }
    steps = [{**step_defaults, **step} for step in steps]

    record = {
        "trajectory_id": injected_id,
        "task_id": "Compute 2 + 3.",
        "agent_config": {
            "framework": "LangGraph",
            "model": "mock-llm-v1",
            "temperature": 0.0,
            "agents_involved": ["answer", "researcher", "reviewer", "retrieval"],
        },
        "outcome": {"status": "FAIL", "success_score": 0.0},
        "fault_injected": True,
        "fault_type": "TOOL_WRONG_ARGUMENT",
        "origin_step": 3,
        "injection_params": {"argument_name": "expression"},
        "num_steps": len(steps),
        "num_agents_involved": 4,
        "source": "INJECTED",
        "split": "TEST",
        "steps": steps,
    }

    (injected_dir / f"{injected_id}.json").write_text(
        json.dumps(record), encoding="utf-8"
    )

    return injected_dir, injected_id


def write_replay(tmp_path, injected_id, baseline_id):
    replay_dir = tmp_path / "replay"
    replay_dir.mkdir(parents=True, exist_ok=True)

    comparison = {
        "baseline_id": baseline_id,
        "injected_id": injected_id,
        "fault_type": "TOOL_WRONG_ARGUMENT",
        "baseline_score": 1.0,
        "injected_score": 0.78,
        "success_delta": 0.22,
        "baseline_checks": [],
        "injected_checks": [],
        "propagation": {
            "origin_step": 3,
            "fault_type": "TOOL_WRONG_ARGUMENT",
            "nodes": [
                {"step_index": 3, "status": "changed", "is_origin": True,
                 "is_root_cause": True},
            ],
            "affected_steps": [3],
            "chain": [{"step_index": 3, "status": "changed"}],
            "edges": [],
            "outcome": {"baseline": {"status": "SUCCESS", "success_score": 1.0},
                        "injected": {"status": "FAIL", "success_score": 0.0}},
        },
        "baseline_replay_deterministic": True,
        "injected_replay_deterministic": False,
        "config": {"provider": "mock", "model": "mock-llm-v1",
                   "temperature": 0.0, "seed": 0, "mock_tools": True},
    }

    payload = {
        "config": comparison["config"],
        "summary": {
            "count": 1,
            "mean_success_delta": 0.22,
            "deterministic_baselines": 1,
            "by_fault": {"TOOL_WRONG_ARGUMENT": {"count": 1, "mean_delta": 0.22}},
        },
        "results": [comparison],
    }

    path = replay_dir / "replay.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    return path


def build_store(tmp_path):
    baseline_dir, baseline_id = write_baseline(tmp_path)
    injected_dir, injected_id = write_injected(tmp_path, baseline_id)
    replay_path = write_replay(tmp_path, injected_id, baseline_id)

    store = DatasetStore(
        baseline_dir=baseline_dir,
        injected_dir=injected_dir,
        replay_path=replay_path,
    )

    return store, baseline_id, injected_id


def make_client(tmp_path):
    store, baseline_id, injected_id = build_store(tmp_path)
    app = create_app(store)
    return app, baseline_id, injected_id


def test_health(tmp_path):
    from fastapi.testclient import TestClient

    app, _, _ = make_client(tmp_path)

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}


def test_meta_reports_counts_and_missing_faults(tmp_path):
    from fastapi.testclient import TestClient

    app, _, _ = make_client(tmp_path)

    with TestClient(app) as client:
        meta = client.get("/api/meta").json()

    assert meta["counts"]["baseline"] == 1
    assert meta["counts"]["injected"] == 1
    assert meta["counts"]["replay"] == 1
    assert "TOOL_WRONG_ARGUMENT" in meta["faultCounts"]
    assert "PLAN_INVALID_DEPENDENCY" in meta["missingFaults"]
    assert len(meta["faultTypes"]) == 20
    assert meta["replaySummary"]["count"] == 1


def test_list_trajectories_filters_by_kind_and_fault(tmp_path):
    from fastapi.testclient import TestClient

    app, baseline_id, injected_id = make_client(tmp_path)

    with TestClient(app) as client:
        all_items = client.get("/api/trajectories").json()
        baselines = client.get("/api/trajectories?kind=baseline").json()
        injected = client.get(
            "/api/trajectories?kind=injected&fault_type=TOOL_WRONG_ARGUMENT"
        ).json()

    assert all_items["total"] == 2
    assert baselines["total"] == 1
    assert injected["total"] == 1
    assert injected["items"][0]["trajectory_id"] == injected_id


def test_trajectory_detail_and_paired_baseline(tmp_path):
    from fastapi.testclient import TestClient

    app, baseline_id, injected_id = make_client(tmp_path)

    with TestClient(app) as client:
        detail = client.get(f"/api/trajectories/{injected_id}").json()
        baseline = client.get(
            f"/api/trajectories/{injected_id}/baseline"
        ).json()

    assert detail["kind"] == "injected"
    assert detail["record"]["fault_type"] == "TOOL_WRONG_ARGUMENT"
    assert detail["baseline_id"] == baseline_id

    assert baseline["baseline_id"] == baseline_id
    assert baseline["record"]["fault_injected"] is False


def test_replay_and_propagation_endpoints(tmp_path):
    from fastapi.testclient import TestClient

    app, _, injected_id = make_client(tmp_path)

    with TestClient(app) as client:
        replay = client.get("/api/replay").json()
        one = client.get(f"/api/replay/{injected_id}").json()
        propagation = client.get(f"/api/propagation/{injected_id}").json()

    assert replay["total"] == 1
    assert replay["summary"]["mean_success_delta"] == 0.22

    assert one["success_delta"] == 0.22
    assert one["injected_score"] == 0.78

    assert propagation["origin_step"] == 3
    assert propagation["fault_type"] == "TOOL_WRONG_ARGUMENT"
    assert propagation["nodes"][0]["is_origin"] is True
    assert propagation["affected_steps"] == [3]


def test_unknown_ids_return_404(tmp_path):
    from fastapi.testclient import TestClient

    app, _, _ = make_client(tmp_path)

    with TestClient(app) as client:
        assert client.get("/api/trajectories/nope").status_code == 404
        assert client.get("/api/replay/nope").status_code == 404
        assert client.get("/api/propagation/nope").status_code == 404


def test_real_dataset_endpoints_serve_full_scale():
    import pytest
    from fastapi.testclient import TestClient

    from dashboard.api import app as live_app

    if not Path("data/trajectories/baseline").is_dir():
        pytest.skip("dataset not present")

    with TestClient(live_app) as client:
        meta = client.get("/api/meta").json()
        listing = client.get(
            "/api/trajectories?kind=injected&limit=5"
        ).json()

    assert meta["counts"]["baseline"] == 160
    assert meta["counts"]["injected"] == 500
    assert meta["counts"]["replay"] == 500
    assert meta["missingFaults"] == ["PLAN_INVALID_DEPENDENCY"]
    assert listing["total"] == 500
    assert len(listing["items"]) == 5
