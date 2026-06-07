"""
Health Agent — analyzes burnout risk, stress impact, work-life balance, wellbeing.
"""
import json
import logging
from typing import Any, Dict, Optional

from .llm_agent import LLMAgent
from quota_manager import get_quota_manager
from deterministic_formulas import (
    compute_stress, compute_burnout_risk,
    compute_work_life_balance, compute_physical_health,
    compute_mental_health,
)

logger = logging.getLogger(__name__)


class HealthAgent(LLMAgent):
    def __init__(self):
        super().__init__("health", "health.txt", temperature=0.5)

    def analyze(
        self,
        decision: str,
        context: dict,
        economic_data: dict,
        core_variables: Optional[dict] = None,
        memory_context: Optional[str] = None,
    ) -> dict:
        if not isinstance(context, dict):
            logger.error("[HealthAgent] context is not a dict: %s", type(context))
            context = {}
        if not isinstance(economic_data, dict):
            logger.error("[HealthAgent] economic_data is not a dict: %s", type(economic_data))
            economic_data = {}
        qm = get_quota_manager()
        cvars = core_variables if isinstance(core_variables, dict) else {}

        if not qm.should_use_llm("health"):
            logger.info("[HealthAgent] Quota mode '%s' — using deterministic formulas", qm.mode)
            return self._deterministic(context, economic_data, cvars)

        prompt = self.build_prompt(
            decision=decision,
            context=json.dumps(context, indent=2, default=str),
            stress_baseline=cvars.get("stress_score", 55),
            work_hours=context.get("work_hours", 45),
            industry=context.get("industry", "technology"),
            location=context.get("location", "Bangalore"),
            memory_context=memory_context or "No prior context available.",
        )

        try:
            result = self.run_structured(prompt)
            self._validate(result)
            return result
        except Exception as exc:
            logger.warning("[HealthAgent] LLM failed: %s — using deterministic", exc)
            return self._deterministic(context, economic_data, cvars)

    def _validate(self, result: dict):
        for key in ["burnout_risk_forecast", "stress_trajectory", "long_term_wellbeing_score", "key_risks", "confidence"]:
            if key not in result:
                raise ValueError(f"Missing key: {key}")

    def _deterministic(self, context: dict, data: dict, cvars: dict) -> dict:
        profile = {}
        years = ["Year1", "Year3", "Year5", "Year7", "Year10"]

        stress_scores = [compute_stress(profile, context, data, y) for y in years]
        burnout = [compute_burnout_risk(profile, context, data, y, s["score"]) for y, s in zip(years, stress_scores)]
        wlb = [compute_work_life_balance(profile, context, y) for y in years]
        phys = [compute_physical_health(profile, context, y, s["score"]) for y, s in zip(years, stress_scores)]
        mental = [compute_mental_health(profile, context, y, s["score"], b["risk"]) for y, s, b in zip(years, stress_scores, burnout)]

        wellbeing_avg = (sum(m["score"] for m in mental) + sum(p["score"] for p in phys)) / (len(mental) + len(phys))

        return {
            "burnout_risk_forecast": burnout,
            "stress_trajectory": stress_scores,
            "work_life_balance": wlb,
            "physical_health_impact": {
                "trajectory": "declining" if phys[0]["score"] > phys[-1]["score"] else "stable",
                "score": round(phys[-1]["score"], 1),
                "narrative": phys[-1]["narrative"],
            },
            "mental_health_assessment": {
                "score": round(mental[-1]["score"], 1),
                "concerns": [
                    "Work stress affecting sleep quality" if stress_scores[-1]["score"] > 55 else "Manageable stress levels",
                    "Reduced social time in mid-career affecting support network",
                ],
                "protective_factors": [
                    "Good income reduces financial stress",
                    "Career progress provides purpose and structure",
                ],
            },
            "long_term_wellbeing_score": round(wellbeing_avg, 1),
            "key_risks": [
                f"Burnout risk peaks at {max(b['risk'] for b in burnout):.0f}/100 in Years 5-7",
                "Sedentary lifestyle health impacts accumulate over time",
                "Reduced sleep quality during high-stress phases affects recovery",
            ],
            "recommendations": [
                "Establish exercise routine in Year1 before career intensifies",
                "Take all allocated leave — recovery is productive",
                "Build therapy/coaching budget into financial plan",
                "Schedule regular digital detox weekends",
            ],
            "confidence": round(0.65 + (100 - stress_scores[-1]["score"]) / 100.0 * 0.2, 2),
        }
