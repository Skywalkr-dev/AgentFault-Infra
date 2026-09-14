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

print("Original:")
print(events[1])

print("\nInjected:")
print(injected[1])
