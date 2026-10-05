import hashlib
import os
import sys

from agent.graph import build_graph
from agent.llm import active_config
from trajectory.events import TrajectoryRecorder
from ingestion.client import send_trajectory

BASELINE_DIR = os.path.join("data", "trajectories", "baseline")


def trajectory_id_for(query: str) -> str:
    digest = hashlib.sha1(query.encode("utf-8")).hexdigest()[:8]
    trajectory_id = f"traj_{digest}"
    attempt = 1

    while os.path.exists(
        os.path.join(BASELINE_DIR, f"{trajectory_id}.jsonl")
    ):
        attempt += 1
        salted = f"{query}#{attempt}".encode("utf-8")
        digest = hashlib.sha1(salted).hexdigest()[:8]
        trajectory_id = f"traj_{digest}"

    return trajectory_id


def ingestion_enabled() -> bool:
    return (os.getenv("INGESTION_ENABLED") or "1").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }


def main() -> int:
    query = " ".join(sys.argv[1:]).strip()

    if not query:
        print("Usage: python main.py <query>")
        return 1

    os.makedirs(BASELINE_DIR, exist_ok=True)

    config = active_config()
    trajectory_id = trajectory_id_for(query)
    recorder = TrajectoryRecorder(trajectory_id)

    recorder.record(
        "trajectory_start",
        input={"query": query},
        metadata={
            "framework": "LangGraph",
            "provider": config.provider,
            "model": config.model,
            "temperature": config.temperature,
        },
    )

    graph = build_graph()
    failed = False

    try:
        result = graph.invoke({
            "query": query,
            "retrieved_context": "",
            "tool_result": "",
            "research": "",
            "review": "",
            "answer": "",
            "recorder": recorder,
        })

        recorder.record(
            "trajectory_end",
            output=result["answer"],
        )

        print(result["answer"])

    except Exception as e:
        failed = True
        recorder.record(
            "trajectory_end",
            status="error",
            output=str(e),
        )

        print(f"Agent failed: {e}")

    finally:
        try:
            recorder.save(
                os.path.join(BASELINE_DIR, f"{trajectory_id}.jsonl")
            )
            print(f"Saved: {BASELINE_DIR}/{trajectory_id}.jsonl")
        except Exception as e:
            failed = True
            print(f"Local save failed: {e}")

        if ingestion_enabled():
            try:
                result = send_trajectory(recorder)
                print(f"Ingested: {result}")
            except Exception as e:
                print(f"Ingestion failed: {e}")

        print(f"\nTrajectory: {trajectory_id}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
