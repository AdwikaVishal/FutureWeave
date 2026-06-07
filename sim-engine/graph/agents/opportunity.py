"""
Opportunity Agent — detects and evaluates career, startup, educational, and network opportunities.
"""
import json
import logging
from typing import Any, Dict, Optional

from .llm_agent import LLMAgent
from quota_manager import get_quota_manager
from deterministic_formulas import (
    compute_career_opportunities, compute_opportunity_score_forecast,
)

logger = logging.getLogger(__name__)


class OpportunityAgent(LLMAgent):
    def __init__(self):
        super().__init__("opportunity", "opportunity.txt", temperature=0.4)

    def analyze(
        self,
        decision: str,
        context: dict,
        economic_data: dict,
        core_variables: Optional[dict] = None,
        memory_context: Optional[str] = None,
    ) -> dict:
        if not isinstance(context, dict):
            logger.error("[OpportunityAgent] context is not a dict: %s", type(context))
            context = {}
        if not isinstance(economic_data, dict):
            logger.error("[OpportunityAgent] economic_data is not a dict: %s", type(economic_data))
            economic_data = {}
        qm = get_quota_manager()
        cvars = core_variables if isinstance(core_variables, dict) else {}

        if not qm.should_use_llm("opportunity"):
            logger.info("[OpportunityAgent] Quota mode '%s' — using deterministic formulas", qm.mode)
            return self._deterministic(context, economic_data, cvars)

        prompt = self.build_prompt(
            decision=decision,
            context=json.dumps(context, indent=2, default=str),
            industry=context.get("industry", "technology"),
            location=context.get("location", "Bangalore"),
            experience_years=cvars.get("experience_years", 2),
            skills=", ".join(context.get("skills", ["Python", "Machine Learning"])),
            memory_context=memory_context or "No prior context available.",
        )

        try:
            result = self.run_structured(prompt)
            self._validate(result)
            return result
        except Exception as exc:
            logger.warning("[OpportunityAgent] LLM failed: %s — using deterministic", exc)
            return self._deterministic(context, economic_data, cvars)

    def _validate(self, result: dict):
        for key in ["career_opportunities", "opportunity_score_forecast", "confidence"]:
            if key not in result:
                raise ValueError(f"Missing key: {key}")

    def _deterministic(self, context: dict, data: dict, cvars: dict) -> dict:
        profile = {}
        if not isinstance(data, dict):
            logger.error("[OpportunityAgent] _deterministic received non-dict data: %s", type(data))
            data = {}
        years = ["Year1", "Year3", "Year5", "Year7", "Year10"]
        industry = context.get("industry", "technology") if isinstance(context, dict) else "technology"

        opps = compute_career_opportunities(profile, context, data) if isinstance(data, dict) else []
        scores = compute_opportunity_score_forecast(profile, context, data) if isinstance(data, dict) else []

        peak_year = max(scores, key=lambda s: s["score"])
        peak_idx = scores.index(peak_year)

        return {
            "career_opportunities": opps,
            "opportunity_score_forecast": scores,
            "emerging_fields": ["AI/ML Engineering", "Product-Led Growth", "Climate Technology", "Health Tech"],
            "skill_gap_analysis": [
                {"skill": "System Design", "importance": 85, "current_level": 50, "urgency": "Year2-4"},
                {"skill": "Executive Communication", "importance": 80, "current_level": 45, "urgency": "Year3-6"},
                {"skill": "Cross-functional Leadership", "importance": 75, "current_level": 40, "urgency": "Year4-7"},
            ],
            "key_insights": [
                f"Your technical skills in {industry} are strongest — leverage this for at least 5 years before pivoting.",
                f"Opportunity landscape peaks in {years[peak_idx]} (score: {peak_year['score']}) when you have enough experience for bold moves.",
                "Consider building management skills starting Year3 to maximize Year7-10 options.",
            ],
            "confidence": round(0.60 + (peak_year["score"] / 100.0) * 0.25, 2),
        }
