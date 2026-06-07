"""
Career Agent — analyzes skill growth, employability, promotions, leadership.
"""
import json
import logging
from typing import Any, Dict, Optional

from .llm_agent import LLMAgent
from quota_manager import get_quota_manager
from deterministic_formulas import (
    compute_skill_growth, compute_employability,
    compute_promotion_timeline, compute_leadership,
)

logger = logging.getLogger(__name__)


class CareerAgent(LLMAgent):
    def __init__(self):
        super().__init__("career", "career.txt", temperature=0.5)

    def analyze(
        self,
        decision: str,
        context: dict,
        economic_data: dict,
        memory_context: Optional[str] = None,
    ) -> dict:
        if not isinstance(context, dict):
            logger.error("[CareerAgent] context is not a dict: %s", type(context))
            context = {}
        if not isinstance(economic_data, dict):
            logger.error("[CareerAgent] economic_data is not a dict: %s", type(economic_data))
            economic_data = {}
        qm = get_quota_manager()
        if not qm.should_use_llm("career"):
            logger.info("[CareerAgent] Quota mode '%s' — using deterministic formulas", qm.mode)
            return self._deterministic(context, economic_data)

        prompt = self.build_prompt(
            decision=decision,
            context=json.dumps(context, indent=2, default=str),
            gdp_growth=economic_data.get("gdp_growth", 6.49),
            industry_health=economic_data.get("industry_health", 78),
            unemployment_rate=economic_data.get("unemployment_rate", 4.22),
            automation_risk=economic_data.get("automation_risk", 15),
            memory_context=memory_context or "No prior context available.",
        )

        try:
            result = self.run_structured(prompt)
            self._validate(result)
            return result
        except Exception as exc:
            logger.warning("[CareerAgent] LLM failed: %s — using deterministic", exc)
            return self._deterministic(context, economic_data)

    def _validate(self, result: dict):
        for key in ["skill_growth_forecast", "employability_forecast", "projected_roles", "confidence"]:
            if key not in result:
                raise ValueError(f"Missing key: {key}")

    def _deterministic(self, context: dict, data: dict) -> dict:
        profile = {"type": "career"}
        years = ["Year1", "Year3", "Year5", "Year7", "Year10"]

        skill = [compute_skill_growth(profile, context, data, y) for y in years]
        employ = [compute_employability(profile, context, data, y) for y in years]
        promo = compute_promotion_timeline(profile, context, data)
        lead_y5 = compute_leadership(profile, context, data, "Year5")
        lead_y10 = compute_leadership(profile, context, data, "Year10")

        projected_roles = [p["title"] for p in promo]

        industry_health = data.get("industry_health", 78)
        automation_risk = data.get("automation_risk", 15)
        skill_avg = sum(s["score"] for s in skill) / len(skill)
        confidence = 0.65 + (industry_health / 100.0) * 0.2 - (automation_risk / 100.0) * 0.1

        return {
            "skill_growth_forecast": skill,
            "employability_forecast": employ,
            "promotion_timeline": [f"{p['title']} ({p['year']})" for p in promo],
            "leadership_trajectory": lead_y5,
            "projected_roles": projected_roles,
            "industry_demand_forecast": {"score": round(industry_health, 1), "narrative": f"Industry health score {industry_health}/100 — demand growing at {round(70 + industry_health * 0.2, 1)}% of peak."},
            "key_milestones": [
                f"First promotion to {projected_roles[0] if len(projected_roles) > 0 else 'next role'} (Year2-3)",
                "First mentorship role (Year4)",
                f"First leadership role as {projected_roles[2] if len(projected_roles) > 2 else 'lead'} (Year5-7)",
                "Industry recognition (Year8-10)",
            ],
            "confidence": round(min(confidence, 0.95), 2),
        }
