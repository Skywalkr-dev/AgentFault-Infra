"""Loading of recorded trajectories into replay-friendly record objects.

Baselines are stored as JSONL event logs; injected trajectories are stored as
JSON documents. Both are normalized to lightweight namespaces that expose the
attributes the ReplayEngine relies on (``steps``, ``trajectory_id``,
``fault_type``, ``origin_step``, ``outcome`` …).
"""

import json
from pathlib import Path
from types import SimpleNamespace

from injector.real_trajectory import events_to_record, load_events


def record_from_dict(data: dict) -> SimpleNamespace:
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


def load_baselines(directory: str | Path) -> dict[str, SimpleNamespace]:
    records: dict[str, SimpleNamespace] = {}

    for path in sorted(Path(directory).glob("*.jsonl")):
        try:
            records[path.stem] = events_to_record(load_events(path))
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[warn] baseline {path.name}: {exc}")

    return records


def load_injected(directory: str | Path) -> dict[str, SimpleNamespace]:
    records: dict[str, SimpleNamespace] = {}

    for path in sorted(Path(directory).glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            records[path.stem] = record_from_dict(data)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[warn] injected {path.name}: {exc}")

    return records
