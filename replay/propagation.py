import json
from dataclasses import dataclass, field
from difflib import SequenceMatcher

FIELD_NAMES = ("agent", "tool", "input", "output", "status", "metadata")


def _short(value, limit: int = 160) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)

    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _fields(step) -> dict:
    return {
        "agent": step.agent_id,
        "tool": step.tool_name,
        "input": step.input,
        "output": step.output,
        "status": step.status,
        "metadata": step.metadata or {},
    }


def _norm(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def step_changes(baseline_step, injected_step) -> list[dict]:
    before = _fields(baseline_step)
    after = _fields(injected_step)
    changes = []

    for name in FIELD_NAMES:
        if _norm(before[name]) != _norm(after[name]):
            changes.append(
                {
                    "field": name,
                    "before": _short(before[name]),
                    "after": _short(after[name]),
                }
            )

    return changes


def _key(step) -> tuple:
    return (step.step_type, step.agent_id)


@dataclass
class ChainNode:
    step_index: int
    step_type: str
    agent: str | None
    status: str
    is_origin: bool
    is_root_cause: bool
    changes: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "step_index": self.step_index,
            "step_type": self.step_type,
            "agent": self.agent,
            "status": self.status,
            "is_origin": self.is_origin,
            "is_root_cause": self.is_root_cause,
            "changes": self.changes,
        }


def align(baseline_steps, injected_steps):
    matcher = SequenceMatcher(
        a=[_key(step) for step in baseline_steps],
        b=[_key(step) for step in injected_steps],
        autojunk=False,
    )
    pairs = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("equal", "replace"):
            block = max(i2 - i1, j2 - j1)
            for offset in range(block):
                base = (
                    baseline_steps[i1 + offset]
                    if i1 + offset < i2
                    else None
                )
                inj = (
                    injected_steps[j1 + offset]
                    if j1 + offset < j2
                    else None
                )
                pairs.append((base, inj))
        elif tag == "delete":
            for offset in range(i1, i2):
                pairs.append((baseline_steps[offset], None))
        elif tag == "insert":
            for offset in range(j1, j2):
                pairs.append((None, injected_steps[offset]))

    return pairs


def propagation_chain(
    baseline,
    injected,
    origin_step=None,
    fault_type=None,
) -> dict:
    nodes = []

    for base, inj in align(baseline.steps, injected.steps):
        if base is not None and inj is not None:
            changes = step_changes(base, inj)
            node = ChainNode(
                step_index=inj.step_index,
                step_type=inj.step_type,
                agent=inj.agent_id,
                status="changed" if changes else "same",
                is_origin=False,
                is_root_cause=bool(inj.is_root_cause),
                changes=changes,
            )
        elif inj is not None:
            node = ChainNode(
                step_index=inj.step_index,
                step_type=inj.step_type,
                agent=inj.agent_id,
                status="added",
                is_origin=False,
                is_root_cause=bool(inj.is_root_cause),
            )
        else:
            node = ChainNode(
                step_index=base.step_index,
                step_type=base.step_type,
                agent=base.agent_id,
                status="removed",
                is_origin=False,
                is_root_cause=False,
            )

        nodes.append(node)

    if origin_step is not None:
        for node in nodes:
            if node.step_index == origin_step:
                node.is_origin = True
                break

    affected = [
        node for node in nodes if node.status in ("changed", "added", "removed")
    ]

    origin_index = origin_step
    if origin_index is None and affected:
        origin_index = affected[0].step_index

    chain = [
        node
        for node in affected
        if origin_index is not None and node.step_index >= origin_index
    ]
    if not chain:
        chain = affected

    edges = [
        [chain[idx].step_index, chain[idx + 1].step_index]
        for idx in range(len(chain) - 1)
    ]

    return {
        "origin_step": origin_index,
        "fault_type": fault_type,
        "nodes": [node.to_dict() for node in nodes],
        "affected_steps": [node.step_index for node in affected],
        "chain": [node.to_dict() for node in chain],
        "edges": edges,
        "outcome": {
            "baseline": {
                "status": baseline.outcome.status,
                "success_score": baseline.outcome.success_score,
            },
            "injected": {
                "status": injected.outcome.status,
                "success_score": injected.outcome.success_score,
            },
        },
    }
