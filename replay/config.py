from dataclasses import asdict, dataclass
import os

MOCK_MODEL = "mock-llm-v1"
GEMINI_MODEL = "gemini-3.6-flash"


@dataclass(frozen=True)
class ReplayConfig:
    """Deterministic replay configuration.

    The replay harness always runs at temperature 0 with mocked tools so a
    trajectory replays identically on every machine and every run.
    """

    provider: str = "mock"
    model: str = MOCK_MODEL
    temperature: float = 0.0
    seed: int = 0
    mock_tools: bool = True

    @classmethod
    def from_env(cls) -> "ReplayConfig":
        provider = (os.getenv("AGENTFAULT_LLM") or "mock").strip().lower()
        model = MOCK_MODEL if provider == "mock" else GEMINI_MODEL

        return cls(
            provider=provider,
            model=model,
            temperature=0.0,
            seed=int(os.getenv("AGENTFAULT_REPLAY_SEED", "0")),
            mock_tools=True,
        )

    def to_dict(self) -> dict:
        return asdict(self)
