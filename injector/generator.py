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
        steps = [
            StepRecord(
                step_index=1,
                step_type="LLM_CALL",
                agent_id="planner",
                input={
                    "task": "Research the given topic and produce a final answer."
                },
                output={
                    "plan": [
                        "retrieve_information",
                        "analyze_information",
                        "calculate_result",
                        "produce_answer",
                    ],
                    "success_criteria": "Answer the task accurately.",
                },
            ),
            StepRecord(
                step_index=2,
                step_type="HANDOFF",
                agent_id="planner",
                input={
                    "task": "Research the given topic.",
                    "responsibility": "research",
                },
                output={
                    "target_agent": "researcher",
                    "context": "Perform research and return relevant findings.",
                },
            ),
            StepRecord(
                step_index=3,
                step_type="RETRIEVAL",
                agent_id="researcher",
                input={
                    "query": "relevant information",
                    "context": "Research the given topic.",
                },
                output={
                    "documents_found": 3,
                },
                retrieved_docs=[
                    {
                        "id": "doc_001",
                        "content": "Relevant research information.",
                        "source": "source_a",
                    },
                    {
                        "id": "doc_002",
                        "content": "Additional supporting information.",
                        "source": "source_b",
                    },
                    {
                        "id": "doc_003",
                        "content": "Background information.",
                        "source": "source_c",
                    },
                ],
            ),
            StepRecord(
                step_index=4,
                step_type="LLM_CALL",
                agent_id="researcher",
                input={
                    "context": "Retrieved research documents.",
                    "documents": ["doc_001", "doc_002", "doc_003"],
                },
                output={
                    "analysis": "The retrieved information supports the requested task."
                },
            ),
            StepRecord(
                step_index=5,
                step_type="TOOL_CALL",
                agent_id="researcher",
                input={
                    "query": "calculate result",
                },
                output={
                    "result": 42,
                },
                tool_name="calculator",
            ),
            StepRecord(
                step_index=6,
                step_type="HANDOFF",
                agent_id="researcher",
                input={
                    "research": "Retrieved and analyzed information.",
                    "tool_result": 42,
                },
                output={
                    "target_agent": "writer",
                    "context": {
                        "research": "Retrieved and analyzed information.",
                        "result": 42,
                    },
                },
            ),
            StepRecord(
                step_index=7,
                step_type="LLM_CALL",
                agent_id="writer",
                input={
                    "research": "Retrieved and analyzed information.",
                    "tool_result": 42,
                    "citation": "doc_001",
                },
                output={
                    "draft": "Research completed successfully."
                },
            ),
            StepRecord(
                step_index=8,
                step_type="LLM_CALL",
                agent_id="writer",
                input={
                    "draft": "Research completed successfully.",
                    "success_criteria": "Answer the task accurately.",
                },
                output={
                    "final_answer": "Research completed successfully."
                },
            ),
        ]

        agents = [
            "planner",
            "researcher",
            "writer",
        ]

        return AgentFaultRecord(
            trajectory_id=trajectory_id,
            task_id=task_id,
            agent_config=AgentConfig(
                framework="LangGraph",
                model="model-name",
                temperature=0,
                agents_involved=agents,
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
            num_agents_involved=len(agents),
            source="NATURAL",
            split="TRAIN",
            steps=steps,
        )
