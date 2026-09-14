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
        input={"location": "Chennai, India"},
        output="Sunny",
        tool="weather_tool",
        status="success",
    ),
]


fault = Fault(
    fault_type=FaultType.TOOL_WRONG_TOOL,
    step=2,
    parameters={
        "original_tool": "weather_tool",
        "injected_tool": "calculator_tool",
    },
    seed=42,
)

injector = FaultInjector()
injected = injector.inject(events, fault)

assert events[1].tool == "weather_tool"
assert injected[1].tool == "calculator_tool"

assert injected[1].metadata["injected_fault"]["type"] == "TOOL_WRONG_TOOL"
assert injected[1].metadata["injected_fault"]["step"] == 2
assert injected[1].metadata["injected_fault"]["seed"] == 42

print("All injector tests passed.")
