import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LifestyleAgent:
    def __init__(self):
        self.name = "lifestyle"

    def analyze(
        self,
        decision: str,
        context: dict,
        economic_data: dict,
        core_variables: Optional[dict] = None,
        memory_context: Optional[str] = None,
    ) -> dict:
        cvars = core_variables if isinstance(core_variables, dict) else {}
        disposable = cvars.get("disposable_income", 0)
        stress = cvars.get("stress_score", 55)
        wlb_raw = context.get("work_hours", 45)
        try:
            wlb = int(wlb_raw)
        except (ValueError, TypeError):
            wlb = 45
        wlb_score = max(0, min(100, 100 - (wlb - 35) * 3))
        fin_score = max(0, min(100, 50 + disposable / 2000))
        stress_penalty = max(0, stress - 40)
        score = max(10, min(95, int(wlb_score * 0.4 + fin_score * 0.35 - stress_penalty * 0.25)))
        return {
            "score": score,
            "reasoning": f"Lifestyle assessment: {score}/100. "
                         f"Work hours ({wlb}h/wk), disposable income (₹{disposable:,}), "
                         f"and stress ({stress}/100) factored into outcome.",
            "confidence": 0.6,
            "agent_name": self.name,
        }
