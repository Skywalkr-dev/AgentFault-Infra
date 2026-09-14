from uuid import uuid4

from agent.graph import build_graph
from trajectory.events import TrajectoryRecorder
from ingestion.client import send_trajectory

graph = build_graph()

trajectory_id = f"traj_{uuid4().hex[:8]}"
recorder = TrajectoryRecorder(trajectory_id)

recorder.record(
    "trajectory_start",
    input={"query": "What is 847 * 293?"},
)

try:
    result = graph.invoke({
        "query": "What is 847 * 293?",
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
    recorder.record(
        "trajectory_end",
        status="error",
        output=str(e),
    )

    print(f"Agent failed: {e}")

finally:
    recorder.save(f"trajectories/{trajectory_id}.jsonl")
    try:
        result = send_trajectory(recorder)
        print(f"Ingested: {result}")
    except Exception as e:
        print(f"Ingestion failed: {e}")

    print(f"\nTrajectory: {trajectory_id}")
