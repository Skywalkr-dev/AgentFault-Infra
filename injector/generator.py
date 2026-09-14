import random

from injector.schema import (
    AgentConfig,
    AgentFaultRecord,
    Outcome,
    StepRecord,
)


class TrajectoryGenerator:
    def __init__(self, seed: int | None = None):
        self.random = random.Random(seed)

    def generate(
        self,
        trajectory_id: str,
        task_id: str,
    ) -> AgentFaultRecord:
        agent_id = "research_agent"

        steps = [
            StepRecord(
                step_index=1,
                step_type="LLM_CALL",
                agent_id=agent_id,
                input={
                    "query": "Research the given topic."
                },
                output={
                    "action": "Retrieve relevant information."
                },
            ),
            StepRecord(
                step_index=2,
                step_type="RETRIEVAL",
                agent_id=agent_id,
                input={
                    "query": "relevant information"
                },
                output={
                    "documents_found": 3
                },
                retrieved_docs=[
                    {
                        "id": "doc_001",
                        "content": "Relevant research information."
                    },
                    {
                        "id": "doc_002",
                        "content": "Additional supporting information."
                    },
                    {
                        "id": "doc_003",
                        "content": "Background information."
                    },
                ],
            ),
            StepRecord(
                step_index=3,
                step_type="LLM_CALL",
                agent_id=agent_id,
                input={
                    "context": "Retrieved research documents."
                },
                output={
                    "action": "Analyze the retrieved information."
                },
            ),
            StepRecord(
                step_index=4,
                step_type="TOOL_CALL",
                agent_id=agent_id,
                input={
                    "query": "calculate result"
                },
                output={
                    "result": 42
                },
                tool_name="calculator",
            ),
            StepRecord(
                step_index=5,
                step_type="LLM_CALL",
                agent_id=agent_id,
                input={
                    "research": "Retrieved and analyzed information.",
                    "tool_result": 42,
                },
                output={
                    "final_answer": "Research completed successfully."
                },
            ),
        ]

        return AgentFaultRecord(
            trajectory_id=trajectory_id,
            task_id=task_id,
            agent_config=AgentConfig(
                framework="LangGraph",
                model="model-name",
                temperature=0,
                agents_involved=[agent_id],
            ),
            outcome=Outcome(
                status="SUCCESS",
                success_score=1.0,
            ),
            fault_injected=False,
            fault_type=None,
            origin_step=None,
            injection_params=None,
            num_steps=len(steps),
            num_agents_involved=1,
            source="NATURAL",
            split="TRAIN",
            steps=steps,
        )
