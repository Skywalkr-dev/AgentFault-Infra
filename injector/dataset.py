import random

from injector.faults import Fault, FaultType
from injector.generator import TrajectoryGenerator
from injector.injector import FaultInjector
from injector.schema import AgentFaultRecord


class DatasetGenerator:
    def __init__(self, seed: int | None = None):
        self.random = random.Random(seed)
        self.injector = FaultInjector()

    def generate(
        self,
        count: int,
    ) -> list[AgentFaultRecord]:
        records = []

        for index in range(1, count + 1):
            trajectory_id = f"AF-{index:04d}"
            task_id = f"TASK-{index:04d}"

            generator = TrajectoryGenerator(
                seed=self.random.randint(0, 1_000_000)
            )

            baseline = generator.generate(
                trajectory_id=trajectory_id,
                task_id=task_id,
            )

            fault = Fault(
                fault_type=FaultType.TOOL_WRONG_ARGUMENT,
                step=4,
                parameters={
                    "operator": "REPLACE_ARGUMENT_VALUE",
                    "argument_name": "query",
                    "original_value": "calculate result",
                    "injected_value": "calculate nonsense",
                },
                seed=self.random.randint(0, 1_000_000),
            )

            injected = self.injector.inject(
                baseline,
                fault,
            )

            records.append(injected)

        return records
