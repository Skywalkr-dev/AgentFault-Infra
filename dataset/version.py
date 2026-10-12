"""AgentFault dataset release metadata."""

DATASET_NAME = "AgentFault-500"
DATASET_VERSION = "1.0.0"
DATASET_SLUG = "agentfault-500"
DATASET_SEED = 42

RELEASE_NOTES = (
    "Initial public release. 160 clean baseline trajectories and 500 "
    "fault-injected trajectories covering 19 of 20 fault types, generated "
    "deterministically (seed 42) with the MockLLM and replayed offline."
)
