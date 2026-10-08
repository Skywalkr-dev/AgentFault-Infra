from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from dashboard.store import DatasetStore

DEFAULT_STORE = None


def get_store() -> DatasetStore:
    global DEFAULT_STORE

    if DEFAULT_STORE is None:
        DEFAULT_STORE = DatasetStore()

    return DEFAULT_STORE


def create_app(store: DatasetStore | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = store or get_store()
        yield

    app = FastAPI(
        title="AgentFault Dashboard API",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def current_store() -> DatasetStore:
        return app.state.store

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/meta")
    def meta():
        return current_store().meta()

    @app.get("/api/trajectories")
    def trajectories(
        kind: str = Query("all", pattern="^(all|baseline|injected)$"),
        fault_type: str | None = None,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        return current_store().list_trajectories(
            kind=kind,
            fault_type=fault_type,
            limit=limit,
            offset=offset,
        )

    @app.get("/api/trajectories/{trajectory_id}")
    def trajectory(trajectory_id: str):
        payload = current_store().get_trajectory(trajectory_id)

        if payload is None:
            raise HTTPException(
                status_code=404, detail="trajectory not found"
            )

        return payload

    @app.get("/api/trajectories/{trajectory_id}/baseline")
    def trajectory_baseline(trajectory_id: str):
        baseline_id = DatasetStore.baseline_id_for(trajectory_id)
        baseline = current_store().get_baseline(baseline_id)

        if baseline is None:
            raise HTTPException(
                status_code=404, detail="paired baseline not found"
            )

        return {
            "baseline_id": baseline_id,
            "injected_id": trajectory_id,
            "record": baseline,
        }

    @app.get("/api/replay")
    def replay(
        fault_type: str | None = None,
        limit: int = Query(100, ge=1, le=1000),
    ):
        store = current_store()
        results = list(store.replay.values())

        if fault_type:
            results = [
                result
                for result in results
                if result.get("fault_type") == fault_type
            ]

        return {
            "summary": store.replay_summary,
            "total": len(results),
            "results": results[:limit],
        }

    @app.get("/api/replay/{injected_id}")
    def replay_one(injected_id: str):
        comparison = current_store().get_replay(injected_id)

        if comparison is None:
            raise HTTPException(
                status_code=404, detail="replay result not found"
            )

        return comparison

    @app.get("/api/propagation/{injected_id}")
    def propagation(injected_id: str):
        chain = current_store().get_propagation(injected_id)

        if chain is None:
            raise HTTPException(
                status_code=404, detail="propagation chain not found"
            )

        return chain

    return app


app = create_app()
