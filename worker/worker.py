"""Stateful replay worker.

Consumes injected trajectories, replays each against its paired baseline with
the deterministic ReplayEngine, and records the comparison. The HTTP surface
(``worker.api``) wraps this class; keeping the logic here makes it directly
unit-testable without a server.
"""

import time
from pathlib import Path

from replay import ReplayConfig, ReplayEngine
from replay.records import load_baselines, load_injected

from worker import metrics

DEFAULT_BASELINE_DIR = Path("data/trajectories/baseline")
DEFAULT_INJECTED_DIR = Path("data/trajectories/injected")


class ReplayWorker:
    def __init__(
        self,
        baseline_dir: str | Path = DEFAULT_BASELINE_DIR,
        injected_dir: str | Path = DEFAULT_INJECTED_DIR,
        config: ReplayConfig | None = None,
        limit: int | None = None,
    ):
        self.config = config or ReplayConfig.from_env()
        self.engine = ReplayEngine(self.config)

        self.baselines = load_baselines(baseline_dir)
        self.injected = load_injected(injected_dir)

        # ``limit`` bounds how many injected records are eligible, which keeps
        # small deployments/tests fast; None means "all available".
        self.ids: list[str] = sorted(self.injected)[:limit] if limit else sorted(self.injected)

        self.processed: dict[str, dict] = {}
        self.failed: dict[str, str] = {}
        self.skipped: dict[str, str] = {}
        self.delta_total = 0.0

        metrics.QUEUE_DEPTH.set(self.queue_depth)

    # ---------------------------------------------------------------- status
    @property
    def queue_depth(self) -> int:
        return sum(
            1
            for injected_id in self.ids
            if injected_id not in self.processed and injected_id not in self.skip_set
        )

    @property
    def skip_set(self) -> set[str]:
        return set(self.failed) | set(self.skipped)

    @property
    def mean_delta(self) -> float:
        if not self.processed:
            return 0.0
        return round(self.delta_total / len(self.processed), 4)

    def status(self) -> dict:
        return {
            "baselines": len(self.baselines),
            "injected": len(self.injected),
            "eligible": len(self.ids),
            "processed": len(self.processed),
            "failed": len(self.failed),
            "skipped": len(self.skipped),
            "queue_depth": self.queue_depth,
            "mean_success_delta": self.mean_delta,
            "config": self.config.to_dict(),
        }

    # ------------------------------------------------------------------ work
    def process_one(self, injected_id: str) -> dict:
        injected = self.injected[injected_id]
        baseline_id = injected_id.split("_fault_")[0]
        baseline = self.baselines.get(baseline_id)

        if baseline is None:
            self.skipped[injected_id] = baseline_id
            metrics.JOBS_SKIPPED.inc()
            metrics.QUEUE_DEPTH.set(self.queue_depth)
            raise KeyError(f"missing baseline {baseline_id}")

        started = time.perf_counter()
        comparison = self.engine.compare(baseline, injected)
        duration = time.perf_counter() - started

        payload = comparison.to_dict()
        self.processed[injected_id] = payload
        self.delta_total += payload["success_delta"]

        metrics.JOBS_PROCESSED.labels(
            fault_type=payload.get("fault_type") or "UNKNOWN"
        ).inc()
        metrics.JOB_DURATION.observe(duration)
        metrics.LAST_DELTA.set(payload["success_delta"])
        metrics.MEAN_DELTA.set(self.mean_delta)
        metrics.QUEUE_DEPTH.set(self.queue_depth)

        return payload

    def process(self, n: int = 1) -> list[dict]:
        """Process up to ``n`` pending jobs; returns the completed payloads."""

        completed = []
        metrics.IN_FLIGHT.inc()

        try:
            for injected_id in list(self.ids):
                if len(completed) >= n:
                    break

                if injected_id in self.processed or injected_id in self.skip_set:
                    continue

                try:
                    completed.append(self.process_one(injected_id))
                except KeyError:
                    # Missing baseline: counted as skipped, keep going.
                    continue
                except Exception:
                    self.failed[injected_id] = "error"
                    metrics.JOBS_FAILED.inc()
                    metrics.QUEUE_DEPTH.set(self.queue_depth)
                    continue
        finally:
            metrics.IN_FLIGHT.dec()

        return completed

    def drain(self) -> int:
        """Process every pending job; returns the number processed."""

        return len(self.process(1_000_000))

    def sweep(self, passes: int = 1) -> int:
        """Replay the whole eligible dataset ``passes`` times.

        A sweep is a determinism/benchmark run (every trajectory is replayed
        from scratch on each pass) and doubles as a sustained CPU workload for
        validating worker autoscaling.
        """

        total = 0

        for _ in range(max(1, passes)):
            self.processed.clear()
            self.failed.clear()
            self.skipped.clear()
            self.delta_total = 0.0
            metrics.QUEUE_DEPTH.set(self.queue_depth)
            total += self.drain()

        return total
