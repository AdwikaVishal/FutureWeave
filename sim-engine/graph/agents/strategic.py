import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class StrategicAgent:
    def __init__(self):
        self.name = "strategic"

    def analyze(
        self,
        decision: str,
        context: dict,
        economic_data: dict,
        core_variables: Optional[dict] = None,
        memory_context: Optional[str] = None,
    ) -> dict:
        gdp = economic_data.get("gdp_growth", 6.0)
        ind_health = economic_data.get("industry_health", 60)
        score = max(20, min(95, int(ind_health * 0.5 + (gdp or 6.0) * 4)))
        return {
            "score": score,
            "reasoning": f"Strategic alignment: {score}/100. "
                         f"Industry health ({ind_health}) and GDP growth ({gdp}%) "
                         f"inform long-term strategic positioning.",
            "confidence": 0.6,
            "agent_name": self.name,
        }
