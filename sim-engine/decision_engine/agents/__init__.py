from __future__ import annotations
from typing import Any, Dict, List
from ..types import AgentOutput, UserProfile, EconomicData, FuturePath, DecisionOption


class BaseAgent:
    name: str = "base"
    def analyze(
        self,
        decision: str,
        profile: UserProfile,
        economic: EconomicData,
        future_paths: Dict[str, FuturePath],
        options: List[DecisionOption],
    ) -> AgentOutput:
        raise NotImplementedError
