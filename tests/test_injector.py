from injector.faults import Fault, FaultType
from injector.injector import FaultInjector
from trajectory.events import TrajectoryEvent


events = [
    TrajectoryEvent(
        trajectory_id="traj_test",
        timestamp="2026-09-15T02:00:00",
        event_type="agent_step",
        step=1,
        agent="test-agent",
        input={"query": "hello"},
        output="thinking",
        status="success",
    ),
    TrajectoryEvent(
        trajectory_id="traj_test",
        timestamp="2026-09-15T02:00:01",
        event_type="tool_call",
        step=2,
        agent="test-agent",
        input={"tool": "calculator"},
        output="42",
        tool="calculator",
        status="success",
    ),
]


fault = Fault(
    fault_type=FaultType.TOOL_TIMEOUT,
    step=2,
    parameters={"timeout_seconds": 30},
    seed=42,
)

injector = FaultInjector()
injected = injector.inject(events, fault)


assert events[1].status == "success"
assert events[1].output == "42"

assert injected[1].trajectory_id == "traj_test_fault_tool_timeout_step_2"
assert injected[1].status == "error"
assert injected[1].output == "Injected tool timeout"

assert injected[1].metadata["injected_fault"]["type"] == "tool_timeout"
assert injected[1].metadata["injected_fault"]["step"] == 2
assert injected[1].metadata["injected_fault"]["seed"] == 42

print("All injector tests passed.")
