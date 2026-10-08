from dataclasses import asdict
import json
from pathlib import Path

from injector.faults import FaultType
from injector.real_trajectory import events_to_record, load_events

ALL_FAULT_TYPES = [fault.value for fault in FaultType]


class DatasetStore:
    def __init__(
        self,
        baseline_dir: str | Path = "data/trajectories/baseline",
        injected_dir: str | Path = "data/trajectories/injected",
        replay_path: str | Path = "data/replay/replay.json",
    ):
        self.baseline_dir = Path(baseline_dir)
        self.injected_dir = Path(injected_dir)
        self.replay_path = Path(replay_path)

        self.baselines: dict[str, dict] = {}
        self.injected: dict[str, dict] = {}
        self.replay: dict[str, dict] = {}
        self.replay_summary: dict = {}

        self.load()

    def load(self) -> None:
        self.baselines = {}
        self.injected = {}
        self.replay = {}
        self.replay_summary = {}

        if self.baseline_dir.is_dir():
            for path in sorted(self.baseline_dir.glob("*.jsonl")):
                try:
                    record = events_to_record(load_events(path))
                    self.baselines[path.stem] = asdict(record)
                except Exception:
                    continue

        if self.injected_dir.is_dir():
            for path in sorted(self.injected_dir.glob("*.json")):
                try:
                    self.injected[path.stem] = json.loads(
                        path.read_text(encoding="utf-8")
                    )
                except Exception:
                    continue

        if self.replay_path.is_file():
            try:
                payload = json.loads(
                    self.replay_path.read_text(encoding="utf-8")
                )
                self.replay_summary = payload.get("summary", {})
                for result in payload.get("results", []):
                    self.replay[result["injected_id"]] = result
            except Exception:
                pass

    @staticmethod
    def baseline_id_for(injected_id: str) -> str:
        return injected_id.split("_fault_")[0]

    @staticmethod
    def _summary(record: dict) -> dict:
        return {
            "trajectory_id": record.get("trajectory_id"),
            "task_id": record.get("task_id"),
            "fault_injected": record.get("fault_injected", False),
            "fault_type": record.get("fault_type"),
            "origin_step": record.get("origin_step"),
            "num_steps": record.get("num_steps"),
            "num_agents_involved": record.get("num_agents_involved"),
            "source": record.get("source"),
            "split": record.get("split"),
            "outcome": record.get("outcome"),
            "agent_config": record.get("agent_config"),
        }

    def meta(self) -> dict:
        fault_counts: dict[str, int] = {}

        for record in self.injected.values():
            fault_type = record.get("fault_type") or "UNKNOWN"
            fault_counts[fault_type] = fault_counts.get(fault_type, 0) + 1

        step_type_count: dict[str, int] = {}

        for record in (
            list(self.baselines.values()) + list(self.injected.values())
        ):
            for step in record.get("steps", []):
                step_type = step.get("step_type", "?")
                step_type_count[step_type] = (
                    step_type_count.get(step_type, 0) + 1
                )

        return {
            "counts": {
                "baseline": len(self.baselines),
                "injected": len(self.injected),
                "replay": len(self.replay),
            },
            "faultCounts": fault_counts,
            "faultTypes": ALL_FAULT_TYPES,
            "missingFaults": [
                fault for fault in ALL_FAULT_TYPES
                if fault not in fault_counts
            ],
            "stepTypeCount": step_type_count,
            "replaySummary": self.replay_summary,
            "config": (self.replay_summary or {}).get("config"),
        }

    def list_trajectories(
        self,
        kind: str = "all",
        fault_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        items = []

        if kind in ("all", "baseline"):
            for record in self.baselines.values():
                items.append(
                    {"kind": "baseline", **self._summary(record)}
                )

        if kind in ("all", "injected"):
            for record in self.injected.values():
                if fault_type and record.get("fault_type") != fault_type:
                    continue
                items.append(
                    {"kind": "injected", **self._summary(record)}
                )

        total = len(items)
        items.sort(key=lambda item: item.get("trajectory_id") or "")

        return {
            "total": total,
            "items": items[offset: offset + limit],
        }

    def get_baseline(self, trajectory_id: str) -> dict | None:
        return self.baselines.get(trajectory_id)

    def get_injected(self, trajectory_id: str) -> dict | None:
        return self.injected.get(trajectory_id)

    def get_trajectory(self, trajectory_id: str) -> dict | None:
        injected = self.get_injected(trajectory_id)

        if injected is not None:
            return {
                "kind": "injected",
                "record": injected,
                "baseline_id": self.baseline_id_for(trajectory_id),
            }

        baseline = self.get_baseline(trajectory_id)

        if baseline is not None:
            return {
                "kind": "baseline",
                "record": baseline,
                "baseline_id": trajectory_id,
            }

        return None

    def get_replay(self, injected_id: str) -> dict | None:
        return self.replay.get(injected_id)

    def get_propagation(self, injected_id: str) -> dict | None:
        comparison = self.replay.get(injected_id)

        if comparison is None:
            return None

        return {
            "injected_id": injected_id,
            "baseline_id": comparison.get("baseline_id"),
            "fault_type": comparison.get("fault_type"),
            **comparison.get("propagation", {}),
        }
