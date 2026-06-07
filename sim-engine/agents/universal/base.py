from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentOutput:
    score: float
    reasoning: str
    evidence: list[str]
    confidence: float


class BaseAgent:
    name: str = "base"

    def evaluate(
        self,
        timelines: dict[str, dict[str, dict[str, float]]],
        decision_type: str,
        anchors: dict,
    ) -> AgentOutput:
        raise NotImplementedError
