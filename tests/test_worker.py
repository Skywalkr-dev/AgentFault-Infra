from pathlib import Path

import pytest

from tests.test_dashboard_api import write_baseline, write_injected
from worker.api import create_app
from worker.worker import ReplayWorker


def build_worker(tmp_path, limit=None):
    baseline_dir, baseline_id = write_baseline(tmp_path)
    injected_dir, injected_id = write_injected(tmp_path, baseline_id)

    worker = ReplayWorker(
        baseline_dir=baseline_dir,
        injected_dir=injected_dir,
        limit=limit,
    )

    return worker, injected_id


def test_worker_loads_and_reports_status(tmp_path):
    worker, _ = build_worker(tmp_path)
    status = worker.status()

    assert status["baselines"] == 1
    assert status["injected"] == 1
    assert status["queue_depth"] == 1
    assert status["processed"] == 0
    assert status["config"]["provider"] == "mock"


def test_process_one_produces_comparison(tmp_path):
    worker, injected_id = build_worker(tmp_path)
    job = worker.process_one(injected_id)

    assert job["injected_id"] == injected_id
    assert job["fault_type"] == "TOOL_WRONG_ARGUMENT"
    assert job["baseline_id"] == "traj_b1"
    assert 0.0 <= job["injected_score"] <= 1.0
    assert worker.processed[injected_id] is job
    assert worker.status()["queue_depth"] == 0


def test_replay_is_deterministic(tmp_path):
    worker, injected_id = build_worker(tmp_path)

    first = worker.process_one(injected_id)
    worker.processed.clear()
    second = worker.process_one(injected_id)

    assert first["injected_score"] == second["injected_score"]
    assert first["success_delta"] == second["success_delta"]
    assert first["propagation"] == second["propagation"]


def test_missing_baseline_is_skipped(tmp_path):
    baseline_dir, _ = write_baseline(tmp_path)
    injected_dir, injected_id = write_injected(tmp_path, "traj_missing")

    worker = ReplayWorker(
        baseline_dir=baseline_dir, injected_dir=injected_dir
    )

    completed = worker.process(5)
    assert completed == []
    assert injected_id in worker.skipped


def test_sweep_replays_every_pass(tmp_path):
    worker, _ = build_worker(tmp_path)

    jobs = worker.sweep(passes=3)
    assert jobs == 3

    status = worker.status()
    assert status["processed"] == 1
    assert status["queue_depth"] == 0


def test_worker_api_endpoints(tmp_path):
    from fastapi.testclient import TestClient

    worker, injected_id = build_worker(tmp_path)
    app = create_app(worker)

    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}

        ready = client.get("/readyz").json()
        assert ready["ready"] is True
        assert ready["queue_depth"] == 1

        work = client.post("/work?n=1").json()
        assert work["processed"] == 1
        assert work["jobs"][0]["injected_id"] == injected_id

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "agentfault_worker_queue_depth" in metrics.text

        sweep = client.post("/sweep?passes=2").json()
        assert sweep["jobs"] == 2


def test_real_dataset_worker_drains_full_batch():
    if not Path("data/trajectories/injected").is_dir():
        pytest.skip("dataset not present")

    worker = ReplayWorker()
    assert worker.status()["injected"] == 500
    assert worker.drain() == 500
    assert worker.status()["queue_depth"] == 0
    assert 0.0 < worker.status()["mean_success_delta"] < 0.5
