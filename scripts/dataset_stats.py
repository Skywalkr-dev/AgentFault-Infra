import json
from collections import Counter
from pathlib import Path
from statistics import mean

from injector.real_trajectory import (
    events_to_record,
    load_events,
)


BASELINE_DIR = Path("data/trajectories/baseline")
INJECTED_DIR = Path("data/trajectories/injected")


def load_baselines():
    records = []

    for path in sorted(BASELINE_DIR.glob("*.jsonl")):
        try:
            events = load_events(path)
            record = events_to_record(events)
            records.append(record)
        except Exception as e:
            print(
                f"Warning: failed to load {path.name}: {e}"
            )

    return records


def load_injected():
    records = []

    for path in sorted(INJECTED_DIR.glob("*.json")):
        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as f:
                data = json.load(f)

            records.append(data)

        except Exception as e:
            print(
                f"Warning: failed to load {path.name}: {e}"
            )

    return records


def print_distribution(title, counter):
    print()
    print(f"=== {title} ===")

    if not counter:
        print("None")
        return

    for key, count in sorted(
        counter.items(),
        key=lambda item: (-item[1], str(item[0])),
    ):
        print(
            f"{str(key):40} {count}"
        )


def get_steps(record):
    if isinstance(record, dict):
        return record.get("steps", [])

    return record.steps


def get_step_type(step):
    if isinstance(step, dict):
        return step.get("step_type")

    return step.step_type


def get_agent_count(record):
    if isinstance(record, dict):
        return record.get(
            "num_agents_involved",
            0,
        )

    return record.num_agents_involved


def step_statistics(records):
    step_counts = [
        len(get_steps(record))
        for record in records
    ]

    if not step_counts:
        return

    print()
    print("=== STEP STATISTICS ===")

    print(
        f"Average steps: {mean(step_counts):.2f}"
    )
    print(
        f"Minimum steps: {min(step_counts)}"
    )
    print(
        f"Maximum steps: {max(step_counts)}"
    )


def agent_statistics(records):
    agent_counts = [
        get_agent_count(record)
        for record in records
    ]

    if not agent_counts:
        return

    print()
    print("=== AGENT STATISTICS ===")

    print(
        f"Average agents: {mean(agent_counts):.2f}"
    )
    print(
        f"Minimum agents: {min(agent_counts)}"
    )
    print(
        f"Maximum agents: {max(agent_counts)}"
    )


def baseline_stats(records):
    step_types = Counter()

    for record in records:
        for step in get_steps(record):
            step_types[
                get_step_type(step)
            ] += 1

    print_distribution(
        "BASELINE STEP TYPES",
        step_types,
    )

    step_statistics(records)
    agent_statistics(records)


def injected_stats(records):
    fault_types = Counter()
    step_types = Counter()
    fault_step_types = Counter()

    for record in records:
        fault_type = record.get(
            "fault_type"
        )

        fault_types[fault_type] += 1

        for step in record.get(
            "steps",
            [],
        ):
            step_type = step.get(
                "step_type"
            )

            step_types[step_type] += 1

            if step.get(
                "is_root_cause"
            ) is True:
                fault_step_types[
                    (fault_type, step_type)
                ] += 1

    print_distribution(
        "FAULT TYPES",
        fault_types,
    )

    print_distribution(
        "INJECTED STEP TYPES",
        step_types,
    )

    print()
    print("=== FAULT BY ROOT-CAUSE STEP TYPE ===")

    for (
        (fault_type, step_type),
        count,
    ) in sorted(
        fault_step_types.items(),
        key=lambda item: (
            str(item[0][0]),
            str(item[0][1]),
        ),
    ):
        print(
            f"{fault_type:40} "
            f"{step_type:15} "
            f"{count}"
        )

    step_statistics(records)
    agent_statistics(records)

    print()
    print("=== FAULT COVERAGE ===")

    expected_faults = {
        "PLAN_MISSING_STEP",
        "PLAN_INCORRECT_SUCCESS_CRITERIA",
        "PLAN_INVALID_DEPENDENCY",
        "TOOL_WRONG_TOOL",
        "TOOL_WRONG_ARGUMENT",
        "TOOL_UNNECESSARY_CALL",
        "TOOL_FAILED_RECOVERY",
        "KNOW_RETRIEVAL_FAILURE",
        "KNOW_CITATION_MISMATCH",
        "KNOW_CONTEXT_TRUNCATION",
        "MA_INCORRECT_HANDOFF",
        "MA_INFORMATION_LOSS",
        "MA_MISSING_RESPONSIBILITY",
        "MA_ROLE_OVERLAP",
        "CTRL_LOOP",
        "CTRL_PREMATURE_TERMINATION",
        "CTRL_EXCESSIVE_EXPLORATION",
        "SEC_PROMPT_INJECTION",
        "SEC_UNAUTHORIZED_ACTION",
        "SEC_CROSS_USER_DATA_LEAKAGE",
    }

    present = set(fault_types)

    for fault_type in sorted(
        expected_faults
    ):
        if fault_type in present:
            print(
                f"[OK]      {fault_type}: "
                f"{fault_types[fault_type]}"
            )
        else:
            print(
                f"[MISSING] {fault_type}"
            )


def main():
    print("AgentFault Dataset Statistics")
    print("=" * 32)

    baselines = load_baselines()
    injected = load_injected()

    print()
    print("=== DATASET SIZE ===")

    print(
        f"Baseline trajectories: "
        f"{len(baselines)}"
    )
    print(
        f"Injected trajectories: "
        f"{len(injected)}"
    )
    print(
        f"Total trajectories: "
        f"{len(baselines) + len(injected)}"
    )

    baseline_stats(baselines)
    injected_stats(injected)

    print()
    print("=== SOURCE / OUTCOME ===")

    source_counts = Counter(
        record.get("source")
        for record in injected
    )

    outcome_counts = Counter(
        record.get(
            "outcome",
            {},
        ).get("status")
        for record in injected
    )

    print_distribution(
        "INJECTED SOURCES",
        source_counts,
    )

    print_distribution(
        "INJECTED OUTCOMES",
        outcome_counts,
    )


if __name__ == "__main__":
    main()
