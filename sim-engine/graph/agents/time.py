import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TimeAgent:
    def __init__(self):
        self.name = "time"

    def analyze(
        self,
        decision: str,
        context: dict,
        economic_data: dict,
        core_variables: Optional[dict] = None,
        memory_context: Optional[str] = None,
    ) -> dict:
        age_raw = context.get("age", 28)
        try:
            age = int(age_raw)
        except (ValueError, TypeError):
            age = 28
        if age < 25:
            score = 85
            reasoning = "Early career — long time horizon for compounding decisions."
        elif age < 35:
            score = 65
            reasoning = "Mid-career — moderate time horizon; key growth decade ahead."
        elif age < 45:
            score = 45
            reasoning = "Established career — shorter time horizon; focus on peak earning years."
        else:
            score = 25
            reasoning = "Late career — limited time horizon; wealth preservation mode."
        return {
            "score": score,
            "reasoning": reasoning,
            "confidence": 0.75,
            "agent_name": self.name,
        }
