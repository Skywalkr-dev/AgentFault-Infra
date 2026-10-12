#!/usr/bin/env python3
"""Export the AgentFault-500 dataset as a versioned, verifiable release.

Produces (deterministically, for a fixed seed):

    <out>/baseline.jsonl   160 clean trajectories (one record per line)
    <out>/injected.jsonl   500 fault-injected trajectories
    <out>/replay.jsonl     500 replay comparisons (score + propagation)
    <out>/manifest.json    version, counts, fault coverage, SHA-256 checksums
    <out>/<slug>-<ver>.zip optional distributable archive (--zip)

The record content is seed-deterministic, so ``content_hash`` is stable across
machines; ``created_at`` records the release time and can be pinned with
``SOURCE_DATE_EPOCH`` for byte-reproducible archives.
"""

import argparse
import hashlib
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dataclasses import asdict

from dataset.version import (
    DATASET_NAME,
    DATASET_SEED,
    DATASET_SLUG,
    DATASET_VERSION,
    RELEASE_NOTES,
)
from injector.faults import FaultType
from injector.real_trajectory import events_to_record, load_events

DEFAULT_BASELINE_DIR = Path("data/trajectories/baseline")
DEFAULT_INJECTED_DIR = Path("data/trajectories/injected")
DEFAULT_REPLAY_PATH = Path("data/replay/replay.json")
DEFAULT_OUT = Path("dataset") / DATASET_SLUG


def canonical_bytes(record: dict) -> bytes:
    return json.dumps(
        record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_baseline_records(directory: str | Path) -> list[dict]:
    records = []

    for path in sorted(Path(directory).glob("*.jsonl")):
        records.append(asdict(events_to_record(load_events(path))))

    records.sort(key=lambda record: record["trajectory_id"])
    return records


def load_injected_records(directory: str | Path) -> list[dict]:
    records = []

    for path in sorted(Path(directory).glob("*.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))

    records.sort(key=lambda record: record["trajectory_id"])
    return records


def load_replay(path: str | Path) -> tuple[list[dict], dict, dict]:
    path = Path(path)

    if not path.is_file():
        return [], {}, {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    results = sorted(
        payload.get("results", []),
        key=lambda result: result["injected_id"],
    )

    return results, payload.get("summary", {}), payload.get("config", {})


def fault_coverage(injected: list[dict]) -> tuple[dict[str, int], list[str]]:
    counts: dict[str, int] = {}

    for record in injected:
        fault = record.get("fault_type") or "UNKNOWN"
        counts[fault] = counts.get(fault, 0) + 1

    known = {fault.value for fault in FaultType}
    missing = sorted(known - set(counts))

    return dict(sorted(counts.items())), missing


def git_commit() -> str | None:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return None


def resolve_created_at(override: str | None) -> str:
    if override:
        return override

    epoch = os.getenv("SOURCE_DATE_EPOCH")

    if epoch:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()

    return datetime.now(timezone.utc).isoformat()


def write_jsonl(path: Path, records: list[dict]) -> bytes:
    data = b"".join(canonical_bytes(record) + b"\n" for record in records)
    path.write_bytes(data)
    return data


def export_dataset(
    baseline_dir: str | Path = DEFAULT_BASELINE_DIR,
    injected_dir: str | Path = DEFAULT_INJECTED_DIR,
    replay_path: str | Path = DEFAULT_REPLAY_PATH,
    out_dir: str | Path = DEFAULT_OUT,
    version: str = DATASET_VERSION,
    created_at: str | None = None,
    include_zip: bool = False,
) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    baselines = load_baseline_records(baseline_dir)
    injected = load_injected_records(injected_dir)
    replay_results, replay_summary, replay_config = load_replay(replay_path)

    baseline_bytes = write_jsonl(out_dir / "baseline.jsonl", baselines)
    injected_bytes = write_jsonl(out_dir / "injected.jsonl", injected)

    files = {
        "baseline.jsonl": {
            "sha256": sha256_bytes(baseline_bytes),
            "bytes": len(baseline_bytes),
            "records": len(baselines),
        },
        "injected.jsonl": {
            "sha256": sha256_bytes(injected_bytes),
            "bytes": len(injected_bytes),
            "records": len(injected),
        },
    }

    if replay_results:
        replay_bytes = write_jsonl(out_dir / "replay.jsonl", replay_results)
        files["replay.jsonl"] = {
            "sha256": sha256_bytes(replay_bytes),
            "bytes": len(replay_bytes),
            "records": len(replay_results),
        }

    fault_counts, missing_faults = fault_coverage(injected)

    manifest = {
        "name": DATASET_NAME,
        "version": version,
        "created_at": resolve_created_at(created_at),
        "release_notes": RELEASE_NOTES,
        "seed": DATASET_SEED,
        "generator": {
            "script": "scripts/export_dataset.py",
            "git_commit": git_commit(),
            "python": platform.python_version(),
        },
        "config": replay_config,
        "counts": {
            "baseline": len(baselines),
            "injected": len(injected),
            "replay": len(replay_results),
            "fault_types_present": len(fault_counts),
            "fault_types_total": len(list(FaultType)),
        },
        "fault_counts": fault_counts,
        "missing_faults": missing_faults,
        "replay_summary": replay_summary,
        "files": files,
        "content_hash": sha256_bytes(baseline_bytes + injected_bytes),
    }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if include_zip:
        import zipfile

        archive = out_dir / f"{DATASET_SLUG}-{version}.zip"

        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for name in sorted(files):
                bundle.write(out_dir / name, arcname=name)
            bundle.write(manifest_path, arcname="manifest.json")

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", type=Path, default=DEFAULT_BASELINE_DIR)
    parser.add_argument("--injected-dir", type=Path, default=DEFAULT_INJECTED_DIR)
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--version", default=DATASET_VERSION)
    parser.add_argument("--created-at", default=None)
    parser.add_argument("--zip", action="store_true")
    args = parser.parse_args()

    manifest = export_dataset(
        baseline_dir=args.baseline_dir,
        injected_dir=args.injected_dir,
        replay_path=args.replay,
        out_dir=args.out,
        version=args.version,
        created_at=args.created_at,
        include_zip=args.zip,
    )

    counts = manifest["counts"]
    print(f"Exported {DATASET_NAME} v{manifest['version']} -> {args.out}")
    print(
        f"  baseline={counts['baseline']} injected={counts['injected']} "
        f"replay={counts['replay']} faults="
        f"{counts['fault_types_present']}/{counts['fault_types_total']}"
    )
    print(f"  content_hash={manifest['content_hash']}")
    print(f"  missing_faults={manifest['missing_faults']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
