"""Prometheus metrics exposed by the replay worker.

The worker is the horizontally-scaled component (see the Helm chart's HPA), so
its metrics drive autoscaling and Stage 6 dashboards.
"""

from prometheus_client import Counter, Gauge, Histogram

JOBS_PROCESSED = Counter(
    "agentfault_worker_jobs_processed_total",
    "Replay comparison jobs completed",
    ["fault_type"],
)

JOBS_FAILED = Counter(
    "agentfault_worker_jobs_failed_total",
    "Replay jobs that raised an exception",
)

JOBS_SKIPPED = Counter(
    "agentfault_worker_jobs_skipped_total",
    "Replay jobs skipped because the paired baseline was missing",
)

QUEUE_DEPTH = Gauge(
    "agentfault_worker_queue_depth",
    "Injected trajectories still awaiting replay",
)

IN_FLIGHT = Gauge(
    "agentfault_worker_in_flight",
    "Replay jobs currently executing",
)

JOB_DURATION = Histogram(
    "agentfault_worker_job_duration_seconds",
    "Wall-clock duration of a single replay comparison",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

MEAN_DELTA = Gauge(
    "agentfault_worker_mean_success_delta",
    "Mean success-score delta across processed jobs",
)

LAST_DELTA = Gauge(
    "agentfault_worker_last_success_delta",
    "Success-score delta of the most recently completed job",
)
