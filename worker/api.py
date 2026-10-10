"""HTTP surface for the replay worker.

Endpoints:
  GET  /healthz    liveness
  GET  /readyz     readiness (dataset loaded)
  GET  /api/status worker counters
  GET  /metrics    Prometheus exposition (scraped by Stage 6 monitoring)
  POST /work       process ``n`` pending replay jobs (query: n, default 1)
  POST /sweep      replay the whole dataset ``passes`` times (benchmark load)
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from worker.worker import ReplayWorker


def default_batch() -> int:
    try:
        return max(1, int(os.environ.get("WORKER_BATCH_SIZE", "1")))
    except ValueError:
        return 1


def create_app(worker: ReplayWorker | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.worker = worker or ReplayWorker()
        yield

    app = FastAPI(title="AgentFault Replay Worker", version="1.0.0", lifespan=lifespan)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz():
        status = app.state.worker.status()
        return {"ready": status["injected"] > 0, **status}

    @app.get("/api/status")
    def status():
        return app.state.worker.status()

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.post("/work")
    def work(n: int = Query(default=None, ge=1, le=1000)):
        batch = n if n is not None else default_batch()
        completed = app.state.worker.process(batch)
        return {
            "processed": len(completed),
            "jobs": [
                {
                    "injected_id": job["injected_id"],
                    "fault_type": job["fault_type"],
                    "success_delta": job["success_delta"],
                }
                for job in completed
            ],
            "status": app.state.worker.status(),
        }

    @app.post("/sweep")
    def sweep(passes: int = Query(default=1, ge=1, le=1000)):
        done = app.state.worker.sweep(passes)
        return {"passes": passes, "jobs": done, "status": app.state.worker.status()}

    return app


app = create_app()
