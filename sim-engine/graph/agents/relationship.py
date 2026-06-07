"""
Relationship Agent — analyzes family stability, social life, relationships, community.
"""
import json
import logging
from typing import Any, Dict, Optional

from .llm_agent import LLMAgent
from quota_manager import get_quota_manager
from deterministic_formulas import (
    compute_family_stability, compute_social_connection,
    compute_relationship_wealth,
)

logger = logging.getLogger(__name__)


class RelationshipAgent(LLMAgent):
    def __init__(self):
        super().__init__("relationship", "relationship.txt", temperature=0.5)

    def analyze(
        self,
        decision: str,
        context: dict,
        economic_data: dict,
        core_variables: Optional[dict] = None,
        memory_context: Optional[str] = None,
    ) -> dict:
        if not isinstance(context, dict):
            logger.error("[RelationshipAgent] context is not a dict: %s", type(context))
            context = {}
        if not isinstance(economic_data, dict):
            logger.error("[RelationshipAgent] economic_data is not a dict: %s", type(economic_data))
            economic_data = {}
        qm = get_quota_manager()
        cvars = core_variables or {}

        if not qm.should_use_llm("relationship"):
            logger.info("[RelationshipAgent] Quota mode '%s' — using deterministic formulas", qm.mode)
            return self._deterministic(context, economic_data)

        prompt = self.build_prompt(
            decision=decision,
            context=json.dumps(context, indent=2, default=str),
            location=context.get("location", "Bangalore"),
            work_hours=context.get("work_hours", 45),
            expected_salary_lpa=cvars.get("expected_salary_lpa", 9.5),
            stress_baseline=cvars.get("stress_score", 55),
            memory_context=memory_context or "No prior context available.",
        )

        try:
            result = self.run_structured(prompt)
            self._validate(result)
            return result
        except Exception as exc:
            logger.warning("[RelationshipAgent] LLM failed: %s — using deterministic", exc)
            return self._deterministic(context, economic_data)

    def _validate(self, result: dict):
        for key in ["family_stability_forecast", "social_connection_forecast", "relationship_wealth_index", "confidence"]:
            if key not in result:
                raise ValueError(f"Missing key: {key}")

    def _deterministic(self, context: dict, data: dict) -> dict:
        profile = {}
        years = ["Year1", "Year3", "Year5", "Year7", "Year10"]
        location = context.get("location", "Bangalore")

        family = [compute_family_stability(profile, context, y) for y in years]
        social = [compute_social_connection(profile, context, y) for y in years]
        wealth = compute_relationship_wealth(
            profile, context,
            family[-1]["score"], social[-1]["score"],
        )

        return {
            "family_stability_forecast": family,
            "social_connection_forecast": social,
            "romantic_relationship_outlook": {
                "probability": round(0.55 + (wealth["index"] / 100.0) * 0.3, 2),
                "quality_score": round(wealth["index"], 1),
                "narrative": (
                    f"{location}'s social scene provides good opportunities for meeting like-minded "
                    f"partners, though career intensity in Years 3-7 may delay serious commitment."
                ),
            },
            "community_support_score": round(social[-1]["score"] * 0.85, 1),
            "relationship_wealth_index": wealth["index"],
            "key_milestones": [
                "Build core friend group by Year2",
                "Deepen 2-3 close friendships by Year5",
                "Establish community roots by Year7",
            ],
            "risk_factors": [
                "Relocation reduces existing social capital initially",
                "Career intensity in Years 3-7 may strain key relationships",
                "Work-from-city separates from family support network",
            ],
            "recommendations": [
                "Invest 8-10 hours/week in relationships intentionally",
                "Join 2-3 community groups in first year",
                "Schedule regular family visits despite career demands",
                "Date intentionally — not just when time allows",
            ],
            "confidence": round(0.60 + (wealth["index"] / 100.0) * 0.2, 2),
        }
