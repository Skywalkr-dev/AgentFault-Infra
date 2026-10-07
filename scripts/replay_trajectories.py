#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from injector.real_trajectory import events_to_record, load_events
from replay import ReplayConfig, ReplayEngine

BASELINE_DIR = Path("data/trajectories/baseline")
INJECTED_DIR = Path("data/trajectories/injected")
DEFAULT_OUT = Path("data/replay/replay.json")


def load_baselines():
    records = {}

    for path in sorted(BASELINE_DIR.glob("*.jsonl")):
        try:
            records[path.stem] = events_to_record(load_events(path))
        except Exception as exc:
            print(f"[warn] baseline {path.name}: {exc}")

    return records


def record_from_dict(data) -> SimpleNamespace:
    steps = [SimpleNamespace(**step) for step in data["steps"]]

    return SimpleNamespace(
        trajectory_id=data["trajectory_id"],
        fault_type=data.get("fault_type"),
        origin_step=data.get("origin_step"),
        outcome=SimpleNamespace(**data["outcome"]),
        steps=steps,
        source=data.get("source"),
        split=data.get("split"),
    )


def load_injected():
    records = {}

    for path in sorted(INJECTED_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            records[path.stem] = record_from_dict(data)
        except Exception as exc:
            print(f"[warn] injected {path.name}: {exc}")

    return records


def build_results(engine, baselines, injected, limit=None, pair=None):
    results = []
    skipped = 0

    for injected_id, injected_record in injected.items():
        if pair and injected_id != pair:
            continue

        base_id = injected_id.split("_fault_")[0]
        baseline = baselines.get(base_id)

        if baseline is None:
            skipped += 1
            continue

        comparison = engine.compare(baseline, injected_record)
        results.append(comparison.to_dict())

        if limit and len(results) >= limit:
            break

    return results, skipped


def summarize(results):
    by_fault = {}

    for result in results:
        fault = result["fault_type"] or "UNKNOWN"
        entry = by_fault.setdefault(fault, {"count": 0, "delta": 0.0})
        entry["count"] += 1
        entry["delta"] += result["success_delta"]

    for entry in by_fault.values():
        entry["mean_delta"] = round(entry["delta"] / entry["count"], 4)

    mean_delta = (
        round(
            sum(result["success_delta"] for result in results) / len(results),
            4,
        )
        if results
        else 0.0
    )

    return {
        "count": len(results),
        "mean_success_delta": mean_delta,
        "deterministic_baselines": sum(
            1 for result in results
            if result["baseline_replay_deterministic"]
        ),
        "by_fault": by_fault,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--pair", type=str, default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--print", action="store_true")
    args = parser.parse_args()

    config = ReplayConfig.from_env()
    engine = ReplayEngine(config)

    baselines = load_baselines()
    injected = load_injected()

    print(f"Baselines: {len(baselines)}")
    print(f"Injected:  {len(injected)}")
    print(f"Replay config: {config.to_dict()}")

    results, skipped = build_results(
        engine, baselines, injected, args.limit, args.pair
    )

    summary = summarize(results)

    print(f"Compared:  {len(results)} pairs ({skipped} unmatched)")
    print(f"Mean success-score delta: {summary['mean_success_delta']}")
    print(
        "Deterministic baseline replays: "
        f"{summary['deterministic_baselines']}/{len(results)}"
    )

    payload = {
        "config": config.to_dict(),
        "summary": summary,
        "results": results,
    }

    if args.print:
        print(json.dumps(payload, indent=2))
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
