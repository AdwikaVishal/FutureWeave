import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HappinessAgent:
    def __init__(self):
        self.name = "happiness"

    def analyze(
        self,
        decision: str,
        context: dict,
        economic_data: dict,
        core_variables: Optional[dict] = None,
        memory_context: Optional[str] = None,
    ) -> dict:
        cvars = core_variables if isinstance(core_variables, dict) else {}
        stress = cvars.get("stress_score", 55)
        savings = cvars.get("savings_rate_pct", 44.3)
        score = max(10, min(90, 70 - stress * 0.3 + savings * 0.15))
        score = int(round(score))
        confidence = round(0.55 + (1.0 - stress / 100.0) * 0.3, 2)
        return {
            "score": score,
            "reasoning": f"Projected happiness: {score}/100. "
                         f"Stress level ({stress}) and savings rate ({savings}%) "
                         f"are primary drivers.",
            "confidence": confidence,
            "agent_name": self.name,
        }
