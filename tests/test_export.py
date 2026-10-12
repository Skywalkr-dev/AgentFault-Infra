import json
from pathlib import Path

import pytest

from scripts.export_dataset import export_dataset
from scripts.verify_export import verify_export
from tests.test_dashboard_api import write_baseline, write_injected, write_replay


def build_inputs(tmp_path):
    baseline_dir, baseline_id = write_baseline(tmp_path)
    injected_dir, injected_id = write_injected(tmp_path, baseline_id)
    replay_path = write_replay(tmp_path, injected_id, baseline_id)

    return baseline_dir, injected_dir, replay_path


def test_export_structure_matches_manifest(tmp_path):
    baseline_dir, injected_dir, replay_path = build_inputs(tmp_path)
    out = tmp_path / "release"

    manifest = export_dataset(
        baseline_dir=baseline_dir,
        injected_dir=injected_dir,
        replay_path=replay_path,
        out_dir=out,
        version="9.9.9",
        created_at="2026-10-12T00:00:00+00:00",
    )

    assert manifest["name"] == "AgentFault-500"
    assert manifest["version"] == "9.9.9"
    assert manifest["created_at"] == "2026-10-12T00:00:00+00:00"
    assert manifest["counts"]["baseline"] == 1
    assert manifest["counts"]["injected"] == 1
    assert manifest["counts"]["replay"] == 1
    assert manifest["fault_counts"] == {"TOOL_WRONG_ARGUMENT": 1}
    assert len(manifest["missing_faults"]) == 19

    assert (out / "baseline.jsonl").is_file()
    assert (out / "injected.jsonl").is_file()
    assert (out / "replay.jsonl").is_file()

    assert set(manifest["files"]) == {
        "baseline.jsonl", "injected.jsonl", "replay.jsonl",
    }
    assert verify_export(out) == []


def test_export_is_deterministic(tmp_path):
    baseline_dir, injected_dir, replay_path = build_inputs(tmp_path)

    first = export_dataset(
        baseline_dir=baseline_dir, injected_dir=injected_dir,
        replay_path=replay_path, out_dir=tmp_path / "a",
        created_at="2026-10-12T00:00:00+00:00",
    )
    second = export_dataset(
        baseline_dir=baseline_dir, injected_dir=injected_dir,
        replay_path=replay_path, out_dir=tmp_path / "b",
        created_at="2026-10-12T00:00:00+00:00",
    )

    assert first["content_hash"] == second["content_hash"]
    assert first["files"] == second["files"]


def test_export_zip_contains_artifacts(tmp_path):
    import zipfile

    baseline_dir, injected_dir, replay_path = build_inputs(tmp_path)
    out = tmp_path / "release"

    export_dataset(
        baseline_dir=baseline_dir, injected_dir=injected_dir,
        replay_path=replay_path, out_dir=out,
        version="1.2.3", include_zip=True,
        created_at="2026-10-12T00:00:00+00:00",
    )

    archive = out / "agentfault-500-1.2.3.zip"
    assert archive.is_file()

    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())

    assert {"baseline.jsonl", "injected.jsonl", "replay.jsonl", "manifest.json"} <= names


def test_verify_detects_tampering(tmp_path):
    baseline_dir, injected_dir, replay_path = build_inputs(tmp_path)
    out = tmp_path / "release"

    export_dataset(
        baseline_dir=baseline_dir, injected_dir=injected_dir,
        replay_path=replay_path, out_dir=out,
        created_at="2026-10-12T00:00:00+00:00",
    )

    assert verify_export(out) == []

    with open(out / "injected.jsonl", "a", encoding="utf-8") as f:
        f.write('{"trajectory_id": "injected_tamper"}\n')

    errors = verify_export(out)
    assert any("injected.jsonl" in error for error in errors)


def test_verify_reports_missing_manifest(tmp_path):
    assert verify_export(tmp_path / "does-not-exist")


def test_real_dataset_export_at_full_scale(tmp_path):
    if not Path("data/trajectories/injected").is_dir():
        pytest.skip("dataset not present")

    out = tmp_path / "agentfault-500"

    manifest = export_dataset(
        out_dir=out, created_at="2026-10-12T00:00:00+00:00"
    )

    counts = manifest["counts"]
    assert counts["baseline"] == 160
    assert counts["injected"] == 500
    assert counts["replay"] == 500
    assert counts["fault_types_present"] == 19
    assert manifest["missing_faults"] == ["PLAN_INVALID_DEPENDENCY"]
    assert abs(manifest["replay_summary"]["mean_success_delta"] - 0.1248) < 1e-9

    assert verify_export(out) == []
