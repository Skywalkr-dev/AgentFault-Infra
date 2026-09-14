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

        derived_id = (
            f"{events[0].trajectory_id}"
            f"_fault_{fault.fault_type.value}"
            f"_step_{fault.step}"
        )

        for event in injected:
            event.trajectory_id = derived_id

            if event.step != fault.step:
                continue

            self._apply_fault(event, fault)

            event.metadata["injected_fault"] = {
                "type": fault.fault_type.value,
                "step": fault.step,
                "parameters": fault.parameters,
                "seed": fault.seed,
            }

        return injected

    def _apply_fault(
        self,
        event: TrajectoryEvent,
        fault: Fault,
    ) -> None:
        if fault.fault_type == FaultType.TOOL_WRONG_ARGUMENT:
            argument_name = fault.parameters["argument_name"]
            injected_value = fault.parameters["injected_value"]

            event.input[argument_name] = injected_value

        elif fault.fault_type == FaultType.TOOL_WRONG_TOOL:
            injected_tool = fault.parameters["injected_tool"]

            event.tool = injected_tool

        else:
            raise ValueError(
                f"Unsupported fault type: {fault.fault_type}"
            )
