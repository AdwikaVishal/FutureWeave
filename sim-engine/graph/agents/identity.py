import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class IdentityAgent:
    def __init__(self):
        self.name = "identity"

    def analyze(
        self,
        decision: str,
        context: dict,
        economic_data: dict,
        core_variables: Optional[dict] = None,
        memory_context: Optional[str] = None,
    ) -> dict:
        interests = context.get("interests", [])
        goals = context.get("goals", [])
        alignment_boost = min(len(interests) * 5, 25) + min(len(goals) * 5, 25)
        score = min(90, max(20, 50 + alignment_boost))
        interest_summary = ", ".join(interests[:3]) if interests else "not specified"
        goal_summary = ", ".join(goals[:3]) if goals else "not specified"
        return {
            "score": score,
            "reasoning": f"Identity alignment score: {score}/100. "
                         f"Interests ({interest_summary}) and goals ({goal_summary}) "
                         f"contribute to personal alignment.",
            "confidence": 0.65,
            "agent_name": self.name,
        }
