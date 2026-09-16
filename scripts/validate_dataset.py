import json
from collections import Counter
from pathlib import Path

from injector.real_trajectory import (
    events_to_record,
    load_events,
)


BASELINE_DIR = Path("data/trajectories/baseline")
INJECTED_DIR = Path("data/trajectories/injected")


EVENT_TYPES = {
    "trajectory_start",
    "trajectory_end",
    "llm_call",
    "tool_call",
    "tool_result",
    "retrieval",
    "handoff",
}


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_baseline(path):
    errors = []

    try:
        events = load_events(path)
    except Exception as e:
        return [f"invalid JSONL: {e}"]

    if not events:
        return ["trajectory contains no events"]

    trajectory_ids = {
        event.trajectory_id
        for event in events
    }

    if len(trajectory_ids) != 1:
        errors.append(
            f"multiple trajectory IDs: {sorted(trajectory_ids)}"
        )

    for index, event in enumerate(events):
        if not event.trajectory_id:
            errors.append(
                f"event {index}: missing trajectory_id"
            )

        if not event.timestamp:
            errors.append(
                f"event {index}: missing timestamp"
            )

        if event.event_type not in EVENT_TYPES:
            errors.append(
                f"event {index}: unknown event_type "
                f"{event.event_type!r}"
            )

        if event.step is None:
            errors.append(
                f"event {index}: missing step"
            )

    start_events = [
        event
        for event in events
        if event.event_type == "trajectory_start"
    ]

    end_events = [
        event
        for event in events
        if event.event_type == "trajectory_end"
    ]

    if len(start_events) != 1:
        errors.append(
            f"expected 1 trajectory_start, "
            f"found {len(start_events)}"
        )

    if len(end_events) != 1:
        errors.append(
            f"expected 1 trajectory_end, "
            f"found {len(end_events)}"
        )

    steps = [
        event.step
        for event in events
        if event.step is not None
    ]

    if steps and steps != sorted(steps):
        errors.append(
            "event steps are not monotonically increasing"
        )

    try:
        events_to_record(events)
    except Exception as e:
        errors.append(
            f"events_to_record failed: {e}"
        )

    return errors


def validate_record(data):
    errors = []

    required = {
        "trajectory_id",
        "task_id",
        "agent_config",
        "outcome",
        "fault_injected",
        "fault_type",
        "origin_step",
        "injection_params",
        "num_steps",
        "num_agents_involved",
        "source",
        "split",
        "steps",
    }

    missing = required - data.keys()

    if missing:
        errors.append(
            f"missing fields: {sorted(missing)}"
        )
        return errors

    steps = data["steps"]

    if not isinstance(steps, list):
        errors.append("steps is not a list")
        return errors

    if data["num_steps"] != len(steps):
        errors.append(
            f"num_steps={data['num_steps']} "
            f"but len(steps)={len(steps)}"
        )

    step_indices = [
        step.get("step_index")
        for step in steps
    ]

    if len(step_indices) != len(set(step_indices)):
        errors.append("duplicate step_index")

    for step in steps:
        step_required = {
            "step_index",
            "step_type",
            "agent_id",
            "input",
            "output",
            "tool_name",
            "retrieved_docs",
            "is_root_cause",
        }

        missing_step = step_required - step.keys()

        if missing_step:
            errors.append(
                "step missing fields: "
                f"{sorted(missing_step)}"
            )

        if step.get("step_type") not in {
            "LLM_CALL",
            "TOOL_CALL",
            "RETRIEVAL",
            "HANDOFF",
        }:
            errors.append(
                f"unknown step_type="
                f"{step.get('step_type')}"
            )

    if data["fault_injected"] is not True:
        errors.append(
            "fault_injected is not true"
        )

    if data["source"] != "INJECTED":
        errors.append(
            f"source={data['source']}"
        )

    if data["fault_type"] is None:
        errors.append(
            "fault_type is null"
        )

    if data["origin_step"] is None:
        errors.append(
            "origin_step is null"
        )

    if data["injection_params"] is None:
        errors.append(
            "injection_params is null"
        )

    outcome = data["outcome"]

    if outcome.get("status") != "FAIL":
        errors.append(
            f"outcome.status={outcome.get('status')}"
        )

    if outcome.get("success_score") != 0.0:
        errors.append(
            "success_score is not 0.0"
        )

    root_steps = [
        step
        for step in steps
        if step.get("is_root_cause") is True
    ]

    if len(root_steps) != 1:
        errors.append(
            f"expected 1 root cause, "
            f"found {len(root_steps)}"
        )
    else:
        root_index = root_steps[0]["step_index"]

        if (
            root_index != data["origin_step"]
            and data["fault_type"]
            != "PLAN_MISSING_STEP"
        ):
            errors.append(
                f"root cause step {root_index} "
                f"!= origin_step "
                f"{data['origin_step']}"
            )

        if root_index not in step_indices:
            errors.append(
                "root cause step does not exist"
            )

    return errors


def validate_baseline_directory(directory):
    files = sorted(
        directory.glob("*.jsonl")
    )

    total = 0
    valid = 0
    invalid = 0

    errors_by_file = {}
    trajectory_ids = set()
    duplicate_ids = []

    event_counts = Counter()

    for path in files:
        total += 1

        errors = validate_baseline(path)

        try:
            events = load_events(path)

            if events:
                trajectory_id = events[0].trajectory_id

                if trajectory_id in trajectory_ids:
                    duplicate_ids.append(
                        trajectory_id
                    )

                trajectory_ids.add(trajectory_id)

                for event in events:
                    event_counts[event.event_type] += 1

        except Exception:
            pass

        if errors:
            invalid += 1
            errors_by_file[path.name] = errors
        else:
            valid += 1

    return {
        "total": total,
        "valid": valid,
        "invalid": invalid,
        "errors": errors_by_file,
        "duplicate_ids": duplicate_ids,
        "event_counts": event_counts,
    }


def validate_injected_directory(directory):
    files = sorted(
        directory.glob("*.json")
    )

    total = 0
    valid = 0
    invalid = 0

    errors_by_file = {}
    trajectory_ids = set()
    duplicate_ids = []

    fault_counts = Counter()

    for path in files:
        total += 1

        try:
            data = load_json(path)
        except Exception as e:
            invalid += 1
            errors_by_file[path.name] = [
                f"invalid JSON: {e}"
            ]
            continue

        trajectory_id = data.get(
            "trajectory_id"
        )

        if trajectory_id in trajectory_ids:
            duplicate_ids.append(
                trajectory_id
            )

        trajectory_ids.add(trajectory_id)

        errors = validate_record(data)

        if errors:
            invalid += 1
            errors_by_file[path.name] = errors
        else:
            valid += 1

        fault_counts[
            data.get("fault_type")
        ] += 1

    return {
        "total": total,
        "valid": valid,
        "invalid": invalid,
        "errors": errors_by_file,
        "duplicate_ids": duplicate_ids,
        "fault_counts": fault_counts,
    }


def print_errors(errors):
    for filename, file_errors in list(
        errors.items()
    )[:20]:
        print()
        print(filename)

        for error in file_errors:
            print(f"  - {error}")

    remaining = len(errors) - 20

    if remaining > 0:
        print()
        print(
            f"... and {remaining} more files"
        )


def main():
    print("=== BASELINES ===")

    baseline = validate_baseline_directory(
        BASELINE_DIR
    )

    print(
        f"Files:   {baseline['total']}"
    )
    print(
        f"Valid:   {baseline['valid']}"
    )
    print(
        f"Invalid: {baseline['invalid']}"
    )

    if baseline["duplicate_ids"]:
        print(
            f"Duplicate IDs: "
            f"{len(baseline['duplicate_ids'])}"
        )

    if baseline["event_counts"]:
        print()
        print("=== BASELINE EVENTS ===")

        for event_type, count in sorted(
            baseline["event_counts"].items()
        ):
            print(
                f"{event_type}: {count}"
            )

    if baseline["errors"]:
        print()
        print("=== BASELINE ERRORS ===")
        print_errors(
            baseline["errors"]
        )

    print()
    print("=== INJECTED ===")

    injected = validate_injected_directory(
        INJECTED_DIR
    )

    print(
        f"Files:   {injected['total']}"
    )
    print(
        f"Valid:   {injected['valid']}"
    )
    print(
        f"Invalid: {injected['invalid']}"
    )

    if injected["duplicate_ids"]:
        print(
            f"Duplicate IDs: "
            f"{len(injected['duplicate_ids'])}"
        )

    print()
    print("=== FAULT DISTRIBUTION ===")

    for fault, count in sorted(
        injected["fault_counts"].items()
    ):
        print(
            f"{fault}: {count}"
        )

    if injected["errors"]:
        print()
        print("=== INJECTED ERRORS ===")
        print_errors(
            injected["errors"]
        )

    print()

    passed = (
        baseline["invalid"] == 0
        and injected["invalid"] == 0
        and not baseline["duplicate_ids"]
        and not injected["duplicate_ids"]
    )

    if passed:
        print("DATASET VALIDATION PASSED")
    else:
        print("DATASET VALIDATION FAILED")


if __name__ == "__main__":
    main()
