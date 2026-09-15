import json
from pathlib import Path
from typing import Any

from injector.schema import (
    AgentConfig,
    AgentFaultRecord,
    Outcome,
    StepRecord,
)
from trajectory.events import TrajectoryEvent


EVENT_TO_STEP_TYPE = {
    "llm_call": "LLM_CALL",
    "tool_call": "TOOL_CALL",
    "retrieval": "RETRIEVAL",
    "handoff": "HANDOFF",
}


def load_events(path: str | Path) -> list[TrajectoryEvent]:
    events = []

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                events.append(
                    TrajectoryEvent(**json.loads(line))
                )

    return events


def events_to_record(
    events: list[TrajectoryEvent],
    fault_type: str | None = None,
    origin_step: int | None = None,
    injection_params: dict[str, Any] | None = None,
) -> AgentFaultRecord:

    if not events:
        raise ValueError("Trajectory contains no events")

    trajectory_id = events[0].trajectory_id

    # Extract task/query from trajectory_start
    start_event = next(
        (e for e in events if e.event_type == "trajectory_start"),
        None,
    )

    task_id = trajectory_id

    if start_event and start_event.input:
        task_id = str(start_event.input)

    # Agents that actually participated
    agents = sorted(
        {
            e.agent
            for e in events
            if e.agent is not None
        }
    )

    steps = []

    for event in events:
        step_type = EVENT_TO_STEP_TYPE.get(event.event_type)

        # Ignore lifecycle events
        if step_type is None:
            continue

        steps.append(
            StepRecord(
                step_index=event.step,
                step_type=step_type,
                agent_id=event.agent or "unknown",
                input=event.input,
                output=event.output,
                tool_name=event.tool,
                retrieved_docs=(
                    event.output
                    if step_type == "RETRIEVAL"
                    else None
                ),
                is_root_cause=(
                    event.step == origin_step
                ),
            )
        )

    fault_injected = fault_type is not None

    return AgentFaultRecord(
        trajectory_id=trajectory_id,
        task_id=task_id,
        agent_config=AgentConfig(
            framework="LangGraph",
            model="gemini-3.6-flash",
            temperature=0.0,
            agents_involved=agents,
        ),
        outcome=Outcome(
            status="FAIL" if fault_injected else "SUCCESS",
            success_score=0.0 if fault_injected else 1.0,
        ),
        fault_injected=fault_injected,
        fault_type=fault_type,
        origin_step=origin_step,
        injection_params=injection_params,
        num_steps=len(steps),
        num_agents_involved=len(agents),
        source="INJECTED" if fault_injected else "NATURAL",
        split="TRAIN",
        steps=steps,
    )
