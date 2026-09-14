from copy import deepcopy

from trajectory.events import TrajectoryEvent
from injector.faults import Fault, FaultType


class FaultInjector:
    def inject(
        self,
        events: list[TrajectoryEvent],
        fault: Fault,
    ) -> list[TrajectoryEvent]:
        injected = deepcopy(events)

        for event in injected:
            if event.step != fault.step:
                continue

            self._apply_fault(event, fault)

        return injected

    def _apply_fault(
        self,
        event: TrajectoryEvent,
        fault: Fault,
    ) -> None:
        if fault.fault_type == FaultType.TOOL_FAILURE:
            event.status = "error"
            event.output = "Injected tool failure"

        elif fault.fault_type == FaultType.TOOL_TIMEOUT:
            event.status = "error"
            event.output = "Injected tool timeout"

        elif fault.fault_type == FaultType.RETRIEVAL_FAILURE:
            event.status = "error"
            event.output = "Injected retrieval failure"

        elif fault.fault_type == FaultType.MALFORMED_OUTPUT:
            event.output = "Injected malformed output"

        else:
            raise ValueError(
                f"Unsupported fault type: {fault.fault_type}"
            )
