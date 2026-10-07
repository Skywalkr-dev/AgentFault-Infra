from dataclasses import dataclass, field

from agent.mock_llm import MockLLM
from agent.retrieval import retrieve
from replay.config import ReplayConfig
from replay.propagation import propagation_chain
from replay.scoring import ScoreReport, evaluate
from replay.tools import MockToolRegistry, ToolCallTrace


def _s(value) -> str:
    return str(value)


@dataclass
class ReplayStepOutcome:
    index: int
    step_type: str
    agent: str | None
    replayed: str
    recorded: str
    matched: bool
    note: str

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "step_type": self.step_type,
            "agent": self.agent,
            "replayed": self.replayed,
            "recorded": self.recorded,
            "matched": self.matched,
            "note": self.note,
        }


@dataclass
class ReplayResult:
    trajectory_id: str
    deterministic: bool
    matched_steps: int
    total_steps: int
    steps: list[ReplayStepOutcome] = field(default_factory=list)
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    config: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "trajectory_id": self.trajectory_id,
            "deterministic": self.deterministic,
            "matched_steps": self.matched_steps,
            "total_steps": self.total_steps,
            "steps": [step.to_dict() for step in self.steps],
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "config": self.config,
        }


@dataclass
class ReplayComparison:
    baseline_id: str
    injected_id: str
    fault_type: str | None
    baseline_score: float
    injected_score: float
    success_delta: float
    baseline_checks: list[dict]
    injected_checks: list[dict]
    propagation: dict
    baseline_replay_deterministic: bool
    injected_replay_deterministic: bool
    config: dict

    def to_dict(self) -> dict:
        return {
            "baseline_id": self.baseline_id,
            "injected_id": self.injected_id,
            "fault_type": self.fault_type,
            "baseline_score": round(self.baseline_score, 4),
            "injected_score": round(self.injected_score, 4),
            "success_delta": round(self.success_delta, 4),
            "baseline_checks": self.baseline_checks,
            "injected_checks": self.injected_checks,
            "propagation": self.propagation,
            "baseline_replay_deterministic": self.baseline_replay_deterministic,
            "injected_replay_deterministic": self.injected_replay_deterministic,
            "config": self.config,
        }


class ReplayEngine:
    """Deterministic, offline replay of recorded trajectories.

    LLM calls are re-executed with the MockLLM (temperature 0) and tool calls
    go through a mocked registry, so a replay never performs real side effects
    and produces identical output on every run.
    """

    def __init__(self, config: ReplayConfig | None = None, llm=None):
        self.config = config or ReplayConfig.from_env()
        self.registry = MockToolRegistry()
        self.llm = llm or MockLLM()

    def replay(self, record) -> ReplayResult:
        outcomes = []
        tool_calls = []

        for position, step in enumerate(record.steps):
            note = ""

            if step.step_type == "RETRIEVAL":
                replayed = (
                    retrieve(step.input)
                    if isinstance(step.input, str)
                    else step.output
                )
                recorded = step.output
                note = "mocked retrieval"

            elif step.step_type == "LLM_CALL":
                replayed = (
                    self.llm.invoke(step.input).content
                    if isinstance(step.input, str)
                    else step.output
                )
                recorded = step.output
                note = f"re-invoked {self.config.provider} llm"

            elif step.step_type == "TOOL_CALL":
                trace = self.registry.trace(step, record.steps, position)
                tool_calls.append(trace)
                replayed = trace.mocked_output
                recorded = trace.recorded_output or ""
                note = "mocked tool call"

            elif step.step_type == "TOOL_RESULT":
                replayed = step.output
                recorded = step.output
                note = "replayed from mocked tool call"

            elif step.step_type == "HANDOFF":
                replayed = step.output
                recorded = step.output
                note = "handoff payload passed through"

            else:
                replayed = step.output
                recorded = step.output
                note = "passthrough"

            outcomes.append(
                ReplayStepOutcome(
                    index=step.step_index,
                    step_type=step.step_type,
                    agent=step.agent_id,
                    replayed=_s(replayed),
                    recorded=_s(recorded),
                    matched=_s(replayed) == _s(recorded),
                    note=note,
                )
            )

        matched = sum(1 for outcome in outcomes if outcome.matched)

        return ReplayResult(
            trajectory_id=record.trajectory_id,
            deterministic=matched == len(outcomes),
            matched_steps=matched,
            total_steps=len(outcomes),
            steps=outcomes,
            tool_calls=tool_calls,
            config=self.config.to_dict(),
        )

    def score(self, record) -> ScoreReport:
        return evaluate(record)

    def compare(self, baseline, injected) -> ReplayComparison:
        baseline_report = self.score(baseline)
        injected_report = self.score(injected)
        propagation = propagation_chain(
            baseline,
            injected,
            origin_step=injected.origin_step,
            fault_type=injected.fault_type,
        )
        baseline_replay = self.replay(baseline)
        injected_replay = self.replay(injected)

        return ReplayComparison(
            baseline_id=baseline.trajectory_id,
            injected_id=injected.trajectory_id,
            fault_type=injected.fault_type,
            baseline_score=baseline_report.score,
            injected_score=injected_report.score,
            success_delta=round(
                baseline_report.score - injected_report.score, 4
            ),
            baseline_checks=[
                check.to_dict() for check in baseline_report.checks
            ],
            injected_checks=[
                check.to_dict() for check in injected_report.checks
            ],
            propagation=propagation,
            baseline_replay_deterministic=baseline_replay.deterministic,
            injected_replay_deterministic=injected_replay.deterministic,
            config=self.config.to_dict(),
        )
