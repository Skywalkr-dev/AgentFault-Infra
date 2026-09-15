import copy
from pathlib import Path
from dataclasses import asdict
import json

from injector.trajectory_io import load_trajectory
from injector.real_trajectory import events_to_record


def main():
    baseline_dir = Path("data/trajectories/baseline")
    injected_dir = Path("data/trajectories/injected")
    injected_dir.mkdir(parents=True, exist_ok=True)

    # Find a real Gemini trajectory containing a tool call
    trajectory_path = None

    for path in baseline_dir.glob("*.jsonl"):
        candidate_events = load_trajectory(path)

        if any(
            event.event_type == "tool_call"
            for event in candidate_events
        ):
            trajectory_path = path
            break

    if trajectory_path is None:
        raise RuntimeError(
            "No baseline trajectory with tool_call found"
        )

    events = load_trajectory(trajectory_path)

    print(f"Using baseline: {trajectory_path}")

    # Never modify baseline
    injected_events = copy.deepcopy(events)

    # Find first tool call
    target = next(
        event
        for event in injected_events
        if event.event_type == "tool_call"
    )

    print(f"Target step: {target.step}")
    print(f"Original input: {target.input}")

    original_input = copy.deepcopy(target.input)

    # TOOL_WRONG_ARGUMENT
    if isinstance(target.input, dict):
        if "service" in target.input:
            target.input["service"] = "invalid_service"
        elif "expression" in target.input:
            target.input["expression"] = "invalid_expression"
        else:
            raise RuntimeError(
                f"Don't know how to mutate tool input: {target.input}"
            )
    else:
        raise RuntimeError(
            f"Expected dict tool input, got "
            f"{type(target.input).__name__}"
        )

    injected_input = copy.deepcopy(target.input)

    injection_params = {
        "operator": "REPLACE_ARGUMENT_VALUE",
        "argument_name": (
            "service"
            if "service" in original_input
            else "expression"
        ),
        "original_value": original_input,
        "injected_value": injected_input,
        "random_seed": None,
    }

    print(f"Injected input: {target.input}")

    # Convert the modified real trajectory
    record = events_to_record(
        injected_events,
        fault_type="TOOL_WRONG_ARGUMENT",
        origin_step=target.step,
        injection_params=injection_params,
    )

    # Unique dataset ID
    record.trajectory_id = (
        f"{record.trajectory_id}"
        f"_INJECTED_TOOL_WRONG_ARGUMENT"
        f"_{target.step}"
    )

    # Save as AgentFault schema JSON
    output_path = (
        injected_dir
        / f"{record.trajectory_id}.json"
    )

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            asdict(record),
            f,
            indent=2,
        )

    print(f"Saved: {output_path}")
    print(f"Fault: {record.fault_type}")
    print(f"Root cause step: {record.origin_step}")
    print(f"Steps: {record.num_steps}")
    print(f"Agents: {record.num_agents_involved}")


if __name__ == "__main__":
    main()
