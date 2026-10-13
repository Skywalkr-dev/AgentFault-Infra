#!/usr/bin/env python3
"""Live end-to-end demo of the AgentFault-Infra pipeline.

Walks through every stage against the checked-in dataset (no network, no
cluster required):

  1. Load baselines, injected trajectories and replay results.
  2. Summarise coverage and the success-score deltas.
  3. Replay one injected trajectory live and show the score breakdown.
  4. Show the propagation chain that connects the fault to the outcome.
  5. Print the exact commands to reproduce regeneration, replay, serving,
     monitoring and deployment.

Usage:
    python scripts/demo.py                      # default sample
    python scripts/demo.py --fault TOOL_FAILED_RECOVERY
    python scripts/demo.py --id traj_..._fault_..._step_3
    python scripts/demo.py --serve              # also start the dashboard API
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.store import DatasetStore
from replay import ReplayConfig, ReplayEngine


def rule(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def show_dataset(store: DatasetStore, config: ReplayConfig) -> None:
    rule("1. Dataset")
    meta = store.meta()
    counts = meta["counts"]

    print(
        f"  baselines : {counts['baseline']:>4}\n"
        f"  injected  : {counts['injected']:>4}\n"
        f"  replays   : {counts['replay']:>4}"
    )
    present = len(meta["faultTypes"]) - len(meta["missingFaults"])
    print(
        f"  fault coverage: {present}/{len(meta['faultTypes'])} "
        f"(missing: {', '.join(meta['missingFaults'])})"
    )

    summary = meta.get("replaySummary") or {}
    if summary:
        print(
            f"  mean success delta: {summary.get('mean_success_delta')} "
            f"({summary.get('deterministic_baselines')}/{summary.get('count')} "
            "baselines replay deterministically)"
        )

    print(
        "  replay config: "
        + ", ".join(
            f"{key}={value}" for key, value in sorted(config.to_dict().items())
        )
    )


def pick_sample(store: DatasetStore, fault: str | None, injected_id: str | None):
    if injected_id:
        if injected_id not in store.injected:
            raise SystemExit(f"unknown injected id: {injected_id}")
        return injected_id

    candidates = sorted(store.injected)

    if fault:
        candidates = [
            i for i in candidates
            if store.injected[i].get("fault_type") == fault
        ]

    if not candidates:
        raise SystemExit("no matching injected trajectories")

    # Prefer a sample with a non-trivial propagation chain and delta.
    def rank(injected_id: str):
        result = store.replay.get(injected_id) or {}
        affected = len(result.get("propagation", {}).get("affected_steps", []))
        return (-affected, injected_id)

    return sorted(candidates, key=rank)[0]


def show_replay(store: DatasetStore, engine: ReplayEngine, injected_id: str) -> None:
    from replay.records import record_from_dict

    injected = record_from_dict(store.injected[injected_id])
    baseline_id = injected_id.split("_fault_")[0]
    baseline = record_from_dict(store.baselines[baseline_id])

    rule("2. Live replay of one fault")
    print(f"  fault      : {injected.fault_type}")
    print(f"  origin step: {injected.origin_step}")
    print(f"  baseline   : {baseline_id}")
    print(f"  injected   : {injected_id}")

    comparison = engine.compare(baseline, injected)

    print()
    print(
        f"  baseline score : {comparison.baseline_score:.4f}   "
        f"(replay deterministic: {comparison.baseline_replay_deterministic})"
    )
    print(
        f"  injected score : {comparison.injected_score:.4f}   "
        f"(replay deterministic: {comparison.injected_replay_deterministic})"
    )
    print(f"  success delta  : {comparison.success_delta:.4f}")

    print()
    print("  success checks (baseline -> injected):")
    injected_checks = {c["name"]: c for c in comparison.injected_checks}

    for check in comparison.baseline_checks:
        after = injected_checks.get(check["name"], {})
        before_ok = "ok  " if check["passed"] else "fail"
        after_ok = "ok  " if after.get("passed") else "fail"
        marker = "  " if check["passed"] == after.get("passed") else "<-"
        weight = check["weight"]
        print(
            f"    [{before_ok} -> {after_ok}] {marker} "
            f"{check['name']:<26} w={weight:.2f}"
        )
        if check["passed"] and not after.get("passed"):
            print(f"         reason: {after.get('reason', '')}")

    propagation = comparison.propagation
    rule("3. Propagation chain")
    print(f"  origin step   : {propagation['origin_step']}")
    print(f"  affected steps: {propagation['affected_steps']}")
    print(f"  edges         : {propagation['edges']}")

    for node in propagation["chain"]:
        flags = []
        if node.get("is_origin"):
            flags.append("origin")
        if node.get("is_root_cause"):
            flags.append("root-cause")
        suffix = f"  [{' '.join(flags)}]" if flags else ""
        print(
            f"    step {node['step_index']:>2} "
            f"{node.get('step_type', '?'):<12} "
            f"{node.get('agent') or '-':<10} "
            f"{node.get('status')}{suffix}"
        )
        for change in node.get("changes", []):
            print(
                f"        {change['field']}: "
                f"{change['before']!r} -> {change['after']!r}"
            )

    outcome = propagation["outcome"]
    print()
    print(
        "  outcome: "
        f"baseline {outcome['baseline']['status']} "
        f"({outcome['baseline']['success_score']}) -> "
        f"injected {outcome['injected']['status']} "
        f"({outcome['injected']['success_score']})"
    )


def show_reproduce() -> None:
    rule("4. Reproduce")
    for line in (
        "regenerate baseline : PYTHONPATH=. python scripts/generate_trajectories.py -n 160",
        "generate faults     : PYTHONPATH=. python scripts/generate_dataset.py",
        "validate            : PYTHONPATH=. python scripts/validate_dataset.py",
        "replay + score      : PYTHONPATH=. python scripts/replay_trajectories.py",
        "export release      : PYTHONPATH=. python scripts/export_dataset.py",
        "verify release      : PYTHONPATH=. python scripts/verify_export.py",
        "serve dashboard     : PYTHONPATH=. uvicorn dashboard.api:app --port 8000",
        "serve worker        : PYTHONPATH=. uvicorn worker.api:app --port 8080",
        "frontend            : cd frontend && npm run build && npm run preview",
        "deploy (Helm+HPA)   : helm install agentfault deploy/helm/agentfault",
        "monitoring          : kubectl apply -f deploy/monitoring",
    ):
        print(f"  {line}")


def serve(host: str, port: int) -> None:
    import uvicorn

    from dashboard.api import app

    print(f"\nServing dashboard API on http://{host}:{port} (Ctrl-C to stop)")
    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fault", default=None, help="fault type to sample")
    parser.add_argument("--id", dest="injected_id", default=None)
    parser.add_argument("--serve", action="store_true", help="start dashboard API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    store = DatasetStore()

    if not store.injected:
        print("No dataset found. Generate it first:")
        show_reproduce()
        return 1

    config = ReplayConfig.from_env()
    engine = ReplayEngine(config)

    show_dataset(store, config)

    injected_id = pick_sample(store, args.fault, args.injected_id)
    show_replay(store, engine, injected_id)

    show_reproduce()

    if args.serve:
        serve(args.host, args.port)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
