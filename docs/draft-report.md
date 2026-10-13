# AgentFault-Infra: A Deterministic Testbed for Fault-Injected Agent Trajectories

**Status: draft.** This document drafts the infrastructure sections of the
AgentFault report. Numbers marked *(verified)* were produced by running the
commands in the appendix on the checked-in code and dataset.

## Abstract

AgentFault-Infra is an offline, deterministic infrastructure for generating,
injecting, replaying and observing failures in multi-agent LLM trajectories.
It ships a 660-trajectory dataset (**AgentFault-500**), a fault taxonomy of 20
injectable fault types, a replay engine that re-executes each trajectory against
a mocked LLM and mocked tools, a scoring harness that measures the resulting
success-score delta, a web dashboard for inspecting faults and their propagation,
and a Kubernetes deployment of the replay workers with CPU-based horizontal
autoscaling and Prometheus/Grafana observability. Every stage runs without
network access and reproduces bit-identical results for a fixed seed.

## 1. Introduction

Reliability work on agent systems needs a reproducible way to *produce* failures,
*label* their root cause, and *observe* how a fault propagates to a task
outcome. Live LLM traffic is non-deterministic, expensive and hard to label at
scale. AgentFault-Infra therefore takes a different route: generate trajectories
with a deterministic mock model, inject a single well-typed fault at a known
step, and replay the result under the same deterministic conditions.

The infrastructure makes three claims that this draft supports:

1. **Determinism.** For a fixed seed, baseline trajectories replay identically.
   Across the full dataset, **500/500 baseline replays are deterministic**
   *(verified)*.
2. **Signal.** Fault injection measurably lowers the graded success score, with
   an overall **mean success delta of 0.1248** *(verified)*.
3. **Operability.** The replay workload is containerised, deployable to
   Kubernetes, horizontally scalable under CPU load, and observable through
   Prometheus and Grafana *(verified against a local kind cluster)*.

## 2. System Overview

```
                      deterministic, offline
  ┌───────────────┐    ┌──────────────────┐    ┌──────────────────┐
  │  Agent graph  │──▶ │  Trajectory log  │──▶ │ Fault injection  │
  │ MockLLM @ t=0 │    │  (JSONL events)  │    │  (20 operators)  │
  └───────────────┘    └──────────────────┘    └────────┬─────────┘
                                                          │
                                ┌─────────────────────────▼─────────┐
                                │        Replay engine              │
                                │ mocked tools · MockLLM · score    │
                                │ + propagation chain (difflib)     │
                                └───────┬───────────────────┬───────┘
                                        │                   │
                     ┌──────────────────▼──┐       ┌────────▼─────────┐
                     │ Dashboard API + SPA │       │ Replay worker(s) │
                     │  (FastAPI + React)  │       │ FastAPI + HPA    │
                     └─────────────────────┘       └────────┬─────────┘
                                                             │
                                        ┌────────────────────▼──────────────┐
                                        │ Prometheus rules + Grafana board  │
                                        └───────────────────────────────────┘
```

Components, by directory:

| Component | Path | Responsibility |
|---|---|---|
| Agent | `agent/` | LangGraph-style graph driven by `MockLLM` at temperature 0 |
| Trajectory | `trajectory/` | Event recorder and JSONL event stream |
| Injector | `injector/` | Taxonomy, operators, dataset generator, validation |
| Replay | `replay/` | Mocked tools, scoring, propagation, engine |
| Dataset | `dataset/`, `scripts/` | AgentFault-500 release, export/verify tooling |
| Dashboard | `dashboard/`, `frontend/` | API + React SPA |
| Worker | `worker/` | Horizontally-scaled replay consumer with Prometheus metrics |
| Deploy | `deploy/`, `Dockerfile.*` | Docker images, Helm chart, HPA, monitoring |

## 3. Dataset Generation and Fault Taxonomy

### 3.1 Taxonomy

Twenty fault types span six categories. Operators mutate the *input*, *output*
or *metadata* of a single target step and mark it as the root cause.

| Category | Faults |
|---|---|
| Planning | `PLAN_MISSING_STEP`, `PLAN_INCORRECT_SUCCESS_CRITERIA`, `PLAN_INVALID_DEPENDENCY` |
| Tool usage | `TOOL_WRONG_TOOL`, `TOOL_WRONG_ARGUMENT`, `TOOL_UNNECESSARY_CALL`, `TOOL_FAILED_RECOVERY` |
| Knowledge | `KNOW_RETRIEVAL_FAILURE`, `KNOW_CITATION_MISMATCH`, `KNOW_CONTEXT_TRUNCATION` |
| Multi-agent | `MA_INCORRECT_HANDOFF`, `MA_INFORMATION_LOSS`, `MA_MISSING_RESPONSIBILITY`, `MA_ROLE_OVERLAP` |
| Control | `CTRL_LOOP`, `CTRL_PREMATURE_TERMINATION`, `CTRL_EXCESSIVE_EXPLORATION` |
| Security | `SEC_PROMPT_INJECTION`, `SEC_UNAUTHORIZED_ACTION`, `SEC_CROSS_USER_DATA_LEAKAGE` |

`PLAN_INVALID_DEPENDENCY` is defined but **not reachable** on this corpus: it
requires a dict-valued plan on an `LLM_CALL` step, whereas all prompts are
strings. Coverage is therefore **19/20** by construction, not by omission.

### 3.2 Generation pipeline

1. `scripts/generate_trajectories.py` samples 160 prompts (calculator, status,
   system-status and knowledge templates) and runs each through `main.py`;
   outputs are JSONL event logs under `data/trajectories/baseline/`.
2. `scripts/generate_dataset.py` runs the `DatasetGenerator` (seed 42) to inject
   faults until 500 injected trajectories exist under
   `data/trajectories/injected/`.
3. `scripts/validate_dataset.py` checks schema and labels for every record.

All randomness is seeded (`seed=42`), the LLM is `MockLLM` (temperature 0), and
IDs are content-derived, so regeneration is reproducible.

### 3.3 Record schema

A record carries `trajectory_id`, `task_id`, `agent_config`, `outcome`,
`fault_injected`, `fault_type`, `origin_step`, `injection_params`, `num_steps`,
`num_agents_involved`, `source`, `split` and `steps`. Each step carries
`step_index`, `step_type` (`RETRIEVAL`, `LLM_CALL`, `TOOL_CALL`, `TOOL_RESULT`,
`HANDOFF`), `agent_id`, `input`, `output`, `tool_name`, `retrieved_docs`,
`is_root_cause`, `status` and `metadata`. Injected records use `split=TEST` and
`source=INJECTED`; baselines use `source=NATURAL`.

### 3.4 Fault distribution (AgentFault-500)

| Fault | n | Fault | n |
|---|--:|---|--:|
| `MA_INFORMATION_LOSS` | 49 | `CTRL_PREMATURE_TERMINATION` | 32 |
| `SEC_CROSS_USER_DATA_LEAKAGE` | 44 | `MA_INCORRECT_HANDOFF` | 21 |
| `KNOW_CITATION_MISMATCH` | 43 | `MA_MISSING_RESPONSIBILITY` | 21 |
| `PLAN_MISSING_STEP` | 41 | `MA_ROLE_OVERLAP` | 18 |
| `PLAN_INCORRECT_SUCCESS_CRITERIA` | 40 | `KNOW_RETRIEVAL_FAILURE` | 13 |
| `CTRL_EXCESSIVE_EXPLORATION` | 39 | `TOOL_WRONG_ARGUMENT` | 12 |
| `KNOW_CONTEXT_TRUNCATION` | 39 | `TOOL_WRONG_TOOL` | 8 |
| `SEC_PROMPT_INJECTION` | 34 | `SEC_UNAUTHORIZED_ACTION` | 6 |
| `CTRL_LOOP` | 33 | `TOOL_UNNECESSARY_CALL` | 4 |
|  |  | `TOOL_FAILED_RECOVERY` | 3 |

## 4. Deterministic Replay Engine

Replay re-executes a trajectory with side effects removed:

- **LLM calls** are re-invoked with `MockLLM` (temperature 0, fixed seed).
- **Tool calls** go through a mocked registry keyed on tool name; the recorded
  `TOOL_RESULT` is compared against the mocked output.
- **Retrieval** is served by the offline `retrieve()` function.

### 4.1 Success scoring

The engine grades each trajectory on seven weighted checks that sum to 1.0:

| Check | Weight | Failure condition |
|---|--:|---|
| `has_final_answer` | 0.18 | last `LLM_CALL` agent is not `answer` / empty |
| `tool_evidence_consistent` | 0.22 | tool output ≠ recorded `TOOL_RESULT` |
| `retrieval_intact` | 0.08 | retrieval output empty/absent |
| `no_step_errors` | 0.12 | a step carries an error status |
| `handoffs_well_formed` | 0.15 | unknown/duplicated agent role, missing responsibility |
| `no_duplicate_steps` | 0.10 | repeated step signatures |
| `no_injection_markers` | 0.15 | injection/anomaly markers present |

The **success delta** is `baseline_score − injected_score` for a paired
baseline/injected trajectory. Healthy baselines score 1.0.

### 4.2 Propagation analysis

For each pair the engine aligns baseline and injected steps with
`difflib.SequenceMatcher` over `(step_type, agent_id)`, diffs the fields
`agent, tool, input, output, status, metadata`, and emits a chain rooted at the
injection's `origin_step`. The chain exposes the origin, the affected steps, and
the before/after of each changed field.

## 5. Dashboard and Visualization

The FastAPI dashboard (`dashboard/api.py`) serves:

| Endpoint | Purpose |
|---|---|
| `GET /api/meta` | counts, fault coverage, step-type histogram, replay summary |
| `GET /api/trajectories` | paginated listing with `kind`/`fault_type` filters |
| `GET /api/trajectories/{id}` | full record; `.../baseline` for the paired baseline |
| `GET /api/replay/{id}` | score breakdown and failed checks |
| `GET /api/propagation/{id}` | propagation chain |

The React SPA adds a pastel-themed detail view with a **Replay comparison**
panel (score bars, delta chip, per-check chips) and a **Propagation chain**
panel (origin → affected steps). When `VITE_API_BASE` is set the SPA reads the
live API; otherwise it falls back to a bundled replay index built at compile
time by `frontend/scripts/build-data.mjs`.

## 6. Reproducibility and Dataset Versioning

`scripts/export_dataset.py` writes a versioned release:

```
dataset/agentfault-500/
  baseline.jsonl    160 clean trajectories
  injected.jsonl    500 fault-injected trajectories
  replay.jsonl      500 score + propagation comparisons
  manifest.json     version, counts, coverage, SHA-256 checksums
```

The manifest records the dataset name/version (`AgentFault-500` / `1.0.0`),
creation time, generator git commit, replay config, per-file SHA-256 and record
counts, fault coverage, the replay summary, and a stable `content_hash`.
`scripts/verify_export.py` recomputes every checksum and the content hash and
exits non-zero on any mismatch, so it can gate a release job. Because record
content is seed-deterministic, `content_hash` is stable across machines; only
`created_at` varies (and can be pinned via `SOURCE_DATE_EPOCH`).

The reference release for this draft has
`content_hash d5d2cca9836a5b63eba6b372cbfda22d8d0f078d6980f86f13a4fb60e51582fd`
and verifies cleanly *(verified)*.

## 7. Deployment and Autoscaling

Two images are built from the repo:

- `Dockerfile.dashboard` — serves the API and prebuilt SPA (`uvicorn dashboard.api:app`).
- `Dockerfile.worker` — runs the replay worker (`uvicorn worker.api:app`).

The Helm chart (`deploy/helm/agentfault/`) deploys both plus a `ServiceMonitor`
(optional) and the Grafana dashboard ConfigMap. The dataset (~6 MB) is baked
into the images, so no persistent volume is needed.

The worker is the horizontally-scaled component. An `autoscaling/v2`
HorizontalPodAutoscaler targets 60% CPU with `minReplicas: 1`,
`maxReplicas: 6`; CPU *requests* are set so the target is meaningful. On a
local kind cluster, driving the worker with `POST /sweep` scaled the deployment
**1 → 2 → 4 → 6** replicas and back *(verified)*.

The worker exposes an HTTP surface for integration and load driving:
`GET /healthz`, `/readyz`, `/api/status`, `/metrics`; `POST /work?n=` and
`POST /sweep?passes=`.

## 8. Observability

The worker publishes Prometheus metrics:

`agentfault_worker_jobs_processed_total{fault_type}`,
`agentfault_worker_jobs_failed_total`, `agentfault_worker_jobs_skipped_total`,
`agentfault_worker_queue_depth`, `agentfault_worker_in_flight`,
`agentfault_worker_job_duration_seconds` (histogram),
`agentfault_worker_mean_success_delta`, `agentfault_worker_last_success_delta`.

`deploy/monitoring/prometheus/agentfault-prometheusrule.yaml` defines six
alerts: worker down, queue backlog, job failures, high job latency, workers at
max replicas, and success-delta regression. `promtool check rules` reports
**SUCCESS: 6 rules found** *(verified)*.

A 10-panel Grafana dashboard
(`deploy/helm/agentfault/dashboards/agentfault-workers.json`) covers replicas
(current/desired), queue depth, mean delta, throughput by fault type, HPA
current/desired/max, p50/p95/p99 latency, queue vs in-flight, worker CPU and
failed/skipped counts. It is shipped as a sidecar-importable ConfigMap
(`grafana_dashboard: "1"`) and was validated against a live
Prometheus+Grafana stack *(verified)*.

## 9. Evaluation

Full-dataset replay (500 pairs):

| Metric | Value |
|---|---|
| Baseline replays deterministic | 500 / 500 |
| Injected replays deterministic | 500 / 500 |
| Mean success delta | 0.1248 |
| Fault coverage | 19 / 20 |

Mean delta by fault *(verified)*:

| Fault | mean Δ | Fault | mean Δ |
|---|--:|---|--:|
| `KNOW_RETRIEVAL_FAILURE` | 0.3500 | `MA_ROLE_OVERLAP` | 0.1500 |
| `TOOL_FAILED_RECOVERY` | 0.2700 | `SEC_*` | 0.1500 |
| `TOOL_WRONG_TOOL` | 0.2200 | `CTRL_LOOP` | 0.1400 |
| `TOOL_WRONG_ARGUMENT` | 0.2200 | `CTRL_PREMATURE_TERMINATION` | 0.1294 |
| `TOOL_UNNECESSARY_CALL` | 0.2200 | `CTRL_EXCESSIVE_EXPLORATION` | 0.1000 |
| `KNOW_CITATION_MISMATCH` | 0.1500 | `PLAN_MISSING_STEP` | 0.0571 |
| `PLAN_INCORRECT_SUCCESS_CRITERIA` | 0.1500 | `MA_INFORMATION_LOSS` | 0.0551 |
| `MA_INCORRECT_HANDOFF` | 0.1500 | `KNOW_CONTEXT_TRUNCATION` | 0.0000 |
| `MA_MISSING_RESPONSIBILITY` | 0.1500 | | |

`KNOW_CONTEXT_TRUNCATION` has a 0.0 delta by design: it only shortens an LLM
prompt string, which none of the structural checks observe. It is retained as a
**structural** fault and is the clearest candidate for a content-aware check in
future work.

## 10. Limitations and Threats to Validity

- **Mock model.** The MockLLM makes the pipeline reproducible and offline but
  not representative of a real model's failure modes; deltas are properties of
  the *harness*, not of a production LLM.
- **Synthetic prompts.** Baseline prompts are template-generated, so the
  distribution of tasks is narrow.
- **Coverage ceiling.** `PLAN_INVALID_DEPENDENCY` is unreachable on string
  prompts; coverage is structurally capped at 19/20.
- **Structural checks only.** `KNOW_CONTEXT_TRUNCATION` is invisible to the
  current checks, so at least one fault's severity is understated.
- **Single fault per trajectory.** The dataset injects exactly one fault per
  record; compound failures are out of scope.

## 11. Future Work

- Content-aware scoring (e.g. semantic equivalence) to observe context
  truncation and other content-only faults.
- Multi-fault and cascading-fault trajectories.
- A real-LLM replay provider behind the same deterministic interface, for
  calibration against the mock.
- A drifting workload generator to exercise the HPA beyond the sweep benchmark.

## Appendix A — Reproduction

```bash
# regenerate and validate the dataset
PYTHONPATH=. python scripts/generate_trajectories.py -n 160
PYTHONPATH=. python scripts/generate_dataset.py
PYTHONPATH=. python scripts/validate_dataset.py

# replay and export a verifiable release
PYTHONPATH=. python scripts/replay_trajectories.py
PYTHONPATH=. python scripts/export_dataset.py
PYTHONPATH=. python scripts/verify_export.py

# run tests
.venv/bin/python -m pytest -q

# serve
PYTHONPATH=. uvicorn dashboard.api:app --port 8000
PYTHONPATH=. uvicorn worker.api:app --port 8080
cd frontend && npm run build && npm run preview

# deploy
helm install agentfault deploy/helm/agentfault
kubectl apply -f deploy/monitoring/prometheus/agentfault-prometheusrule.yaml
```

## Appendix B — Repository layout

```
agent/       deterministic agent graph + MockLLM
trajectory/  event recorder and JSONL stream
injector/    taxonomy, operators, generator, validation
replay/      mocked tools, scoring, propagation, engine
worker/      replay consumer, Prometheus metrics, HTTP API
dashboard/   FastAPI dataset/aggregation API
frontend/    React SPA (pastel theme, replay + propagation views)
dataset/     AgentFault-500 release + version metadata
scripts/     generation, replay, export/verify tooling
deploy/      Helm chart, HPA, ServiceMonitor, Prometheus rules, Grafana board
tests/       unit + end-to-end tests
```
