from dataclasses import dataclass
from enum import Enum
from typing import Any


class FaultType(str, Enum):
    TOOL_FAILURE = "tool_failure"
    TOOL_TIMEOUT = "tool_timeout"
    RETRIEVAL_FAILURE = "retrieval_failure"
    MALFORMED_OUTPUT = "malformed_output"


@dataclass
class Fault:
    fault_type: FaultType
    step: int
    parameters: dict[str, Any]
    seed: int | None = None
