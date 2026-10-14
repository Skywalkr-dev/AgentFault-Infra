# AgentFault-Infra

An offline, deterministic testbed for **fault-injected multi-agent LLM
trajectories**. It generates agent trajectories with a mock model, injects one
well-typed fault at a known step, replays the result under identical conditions,
scores the resulting success drop, and lets you inspect how the fault propagates
to the task outcome — all without network access, API keys, or a live model.

- **Dataset:** AgentFault-500 — 160 clean baselines + 500 fault-injected
  trajectories + 500 replay comparisons (19 of 20 fault types).
- **Determinism:** for a fixed seed, 500/500 baseline replays are identical and
  the release has a stable content hash.
- **Operable:** dashboard API + React SPA, a horizontally-autoscaled replay
  worker, Helm chart, Prometheus alerts and a Grafana dashboard.

The full write-up lives in [`docs/draft-report.md`](docs/draft-report.md).

---

## 1. Requirements

| Tool | Version used | Needed for |
|---|---|---|
| Python | 3.12+ (3.14.7 tested) | everything |
| Node.js + npm | 18+ | frontend |
| Docker | any recent | container images |
| Helm | 3.16+ | Kubernetes deploy |
| kind | 0.24+ | local cluster (optional) |
| kubectl | any recent | Kubernetes (optional) |

Everything except the frontend runs offline. The default LLM is a deterministic
`MockLLM`; no API key is required.

---

## 2. Setup

```bash
git clone <repo-url> AgentFault-Infra
cd AgentFault-Infra

python -m venv .venv
.venv/bin/pip install -r requirements.txt

# test-only dependencies (not in requirements.txt)
.venv/bin/pip install pytest httpx
```

Scripts import the local packages, so run them with `PYTHONPATH=.` from the
repository root (the example commands below already do).

---

## 3. Reproduce the product

The checked-in release under `dataset/agentfault-500/` is a verified snapshot.
The `data/` working tree is **git-ignored**, so to run the dashboard/frontend
from source you regenerate it in this order:

```bash
# 1) 160 clean baseline trajectories -> data/trajectories/baseline/
PYTHONPATH=. .venv/bin/python scripts/generate_trajectories.py -n 160

# 2) inject faults until 500 records -> data/trajectories/injected/  (seed 42)
PYTHONPATH=. .venv/bin/python scripts/generate_dataset.py

# 3) validate every record's schema and labels
PYTHONPATH=. .venv/bin/python scripts/validate_dataset.py

# 4) replay all pairs and write data/replay/replay.json (scores + propagation)
PYTHONPATH=. .venv/bin/python scripts/replay_trajectories.py
```

Expected result after step 4:

```
Baselines: 160
Injected:  500
Mean success-score delta: 0.1248
Deterministic baseline replays: 500/500
```

Regeneration is seed-deterministic (`AGENTFAULT_REPLAY_SEED`, default `0`), so
re-running produces byte-identical records for the same seed.

### Export and verify a versioned release

```bash
# writes dataset/agentfault-500/{baseline,injected,replay}.jsonl + manifest.json
PYTHONPATH=. .venv/bin/python scripts/export_dataset.py

# recompute SHA-256 checksums + content hash from the manifest
PYTHONPATH=. .venv/bin/python scripts/verify_export.py
# -> OK: dataset/agentfault-500 matches its manifest
```

---

## 4. Run the tests

```bash
.venv/bin/python -m pytest -q
# -> 47 passed
```

The suite covers the mock LLM, injector, replay engine, dashboard API, worker,
dataset export and a full end-to-end pipeline.

---

## 5. Run the components

### Live demo (no server needed)

Prints dataset coverage, replays one fault live, and shows the score breakdown
and propagation chain:

```bash
PYTHONPATH=. .venv/bin/python scripts/demo.py
PYTHONPATH=. .venv/bin/python scripts/demo.py --fault TOOL_FAILED_RECOVERY
PYTHONPATH=. .venv/bin/python scripts/demo.py --serve   # also starts the API
```

### Dashboard API (FastAPI, port 8000)

```bash
PYTHONPATH=. .venv/bin/uvicorn dashboard.api:app --port 8000
```

| Endpoint | Description |
|---|---|
| `GET /api/meta` | counts, fault coverage, replay summary |
| `GET /api/trajectories?kind=injected` | paginated listing |
| `GET /api/trajectories/{id}` | full record (`.../baseline` for its pair) |
| `GET /api/replay/{id}` | score breakdown and failed checks |
| `GET /api/propagation/{id}` | propagation chain |

```bash
curl http://127.0.0.1:8000/api/meta
```

### Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev        # dev server, http://localhost:5173
# or a production build + preview:
npm run build      # bundles data/ into public/data, outputs to dist/
npm run preview    # http://localhost:4173
```

To read live data from the API instead of the bundled snapshot, set the base URL
at build/dev time:

```bash
VITE_API_BASE=http://127.0.0.1:8000 npm run dev
```

Routing is hash-based, e.g. `http://localhost:4173/#/t/<trajectory_id>`.

### Replay worker (FastAPI, port 8080)

```bash
PYTHONPATH=. .venv/bin/uvicorn worker.api:app --port 8080
```

| Endpoint | Description |
|---|---|
| `GET /healthz`, `/readyz` | liveness / readiness |
| `GET /api/status` | queue depth, processed/failed, mean delta |
| `GET /metrics` | Prometheus exposition |
| `POST /work?n=8` | process `n` pending replay jobs |
| `POST /sweep?passes=5` | replay the whole dataset (benchmark/load) |

---

## 6. Docker

The dataset is baked into the images, so the containers need no volumes.

```bash
docker build -f Dockerfile.dashboard -t agentfault/dashboard:dev .
docker build -f Dockerfile.worker    -t agentfault/worker:dev .

docker run --rm -p 8000:8000 agentfault/dashboard:dev
docker run --rm -p 8080:8080 agentfault/worker:dev

# trigger work (the worker image has no curl; use python)
docker run -d --name af-worker -p 8080:8080 agentfault/worker:dev
docker exec af-worker python -c \
  "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8080/work?n=8', method='POST'))"
```

---

## 7. Kubernetes (kind + Helm) with autoscaling

```bash
# local cluster
kind create cluster --name agentfault
kind load docker-image agentfault/dashboard:dev agentfault/worker:dev

# metrics-server is required for the CPU-based HPA
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

# install the chart
helm install agentfault deploy/helm/agentfault

kubectl get pods,svc,hpa
kubectl port-forward svc/agentfault-agentfault-dashboard 8000:8000
```

The worker HPA scales `1 → 6` replicas at 60% CPU utilisation. Generate load:

```bash
kubectl exec deploy/agentfault-agentfault-worker -- \
  python -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8080/sweep?passes=5', method='POST'))"
kubectl get hpa -w
```

Preview the rendered manifests without a cluster:

```bash
helm template agentfault deploy/helm/agentfault
helm lint deploy/helm/agentfault
```

---

## 8. Monitoring

- **Alerts:** `deploy/monitoring/prometheus/agentfault-prometheusrule.yaml`
  (6 rules). Validate with
  `promtool check rules` on the extracted `spec.groups`.
- **Grafana board:** `deploy/helm/agentfault/dashboards/agentfault-workers.json`
  (10 panels), shipped as a sidecar-importable ConfigMap
  (`grafana_dashboard: "1"`) when `dashboards.enabled=true`.
- **kube-prometheus-stack overlay:**
  `deploy/monitoring/values-kube-prometheus-stack.yaml`.

Enable the Prometheus Operator ServiceMonitor by setting
`serviceMonitor.enabled=true` in `deploy/helm/agentfault/values.yaml`.

Worker metrics: `agentfault_worker_jobs_processed_total`,
`..._jobs_failed_total`, `..._jobs_skipped_total`, `..._queue_depth`,
`..._in_flight`, `..._job_duration_seconds`, `..._mean_success_delta`,
`..._last_success_delta`.

---

## 9. Project layout

```
agent/       deterministic agent graph + MockLLM
trajectory/  event recorder and JSONL event stream
injector/    fault taxonomy, operators, generator, validation
replay/      mocked tools, scoring, propagation, engine
worker/      replay consumer, Prometheus metrics, HTTP API
dashboard/   FastAPI dataset/aggregation API
frontend/    React SPA (replay + propagation views)
dataset/     AgentFault-500 release + version metadata
scripts/     generation, replay, export/verify, demo
deploy/      Helm chart, HPA, ServiceMonitor, Prometheus rules, Grafana board
tests/       unit + end-to-end tests
docs/        draft report
```

---

## 10. Notes and limitations

- **Offline by default.** `MockLLM` is used everywhere; Gemini is optional and
  requires `GOOGLE_API_KEY` (see `.env.example`).
- **Coverage is 19/20 by design.** `PLAN_INVALID_DEPENDENCY` needs a dict-valued
  plan, which this string-prompt corpus never produces.
- **`KNOW_CONTEXT_TRUNCATION` has a 0.0 score delta** because it only shortens a
  prompt string, which the structural checks do not observe.
- **`data/` and `frontend/node_modules/` are git-ignored**; regenerate them as in
  Section 3 before building the frontend or serving the full dataset.
