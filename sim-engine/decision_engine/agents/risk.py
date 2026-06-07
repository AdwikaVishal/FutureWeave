from __future__ import annotations
import math
import logging
from typing import Any, Dict
from . import BaseAgent
from ..types import AgentOutput, UserProfile, EconomicData, Timeline, YEARS

logger = logging.getLogger(__name__)


class RiskAgent(BaseAgent):
    name = "risk"

    def analyze(self, decision: str, profile: UserProfile, economic: EconomicData, timelines: Dict[str, Timeline]) -> AgentOutput:
        scores = {}
        for yk in YEARS:
            tl_c = timelines.get("Timeline C", {}).years.get(yk)
            tl_a = timelines.get("Timeline A", {}).years.get(yk)
            risk_val = 100 - (tl_c.health if tl_c else 50) * 0.5 + (tl_a.stress if tl_a else 50) * 0.3
            scores[yk] = round(min(100, risk_val), 1)

        base_risk = scores.get("Year10", 50)

        unemployment = economic.unemployment_rate / 10.0
        automation = economic.automation_risk / 100.0
        economic_score = economic.economic_score / 100.0
        employment_score = economic.employment_score / 100.0
        industry_score = economic.industry_score / 100.0

        unemp_risk = unemployment * 30
        auto_risk = automation * 25
        economic_volatility = (1 - economic_score) * 20
        industry_volatility = (1 - industry_score) * 15
        employment_risk = (1 - employment_score) * 10

        combined_risk = base_risk + unemp_risk + auto_risk + economic_volatility + industry_volatility - employment_risk * 0.5
        score = round(min(100, combined_risk), 1)

        downside_prob = min(100, unemp_risk + auto_risk + max(0, (100 - economic_score * 100) * 0.3))
        failure_prob = min(100, base_risk * 0.3 + unemp_risk * 0.4 + auto_risk * 0.3)

        data_used = ["unemployment_rate", "automation_risk", "economic_score", "employment_score", "industry_score"]

        impact_factors = [
            {"factor": "Unemployment Risk", "value": f"{economic.unemployment_rate:.1f}%", "delta": round(unemp_risk, 1)},
            {"factor": "Automation Risk", "value": f"{economic.automation_risk:.0f}%", "delta": round(auto_risk, 1)},
            {"factor": "Economic Volatility", "value": f"{economic.economic_score:.0f}/100", "delta": round(economic_volatility, 1)},
            {"factor": "Industry Volatility", "value": f"{economic.industry_score:.0f}/100", "delta": round(industry_volatility, 1)},
        ]

        evidence = [
            f"Unemployment: {economic.unemployment_rate:.1f}% (+{unemp_risk:.0f}pts risk)",
            f"Automation risk: {economic.automation_risk:.0f}% (+{auto_risk:.0f}pts risk)",
            f"Economic strength: {economic.economic_score:.0f}/100",
            f"Downside probability: {downside_prob:.0f}%",
            f"Failure probability: {failure_prob:.0f}%",
        ]

        if economic.data_freshness.get("unemployment_rate") == "live":
            data_used.append("live_unemployment_data")
            evidence.append("Using live unemployment data from World Bank")

        risk_level = "elevated" if score > 65 else "moderate" if score > 45 else "low"

        reasoning = (
            f"Risk assessment powered by live economic data. "
            f"Unemployment at {economic.unemployment_rate:.1f}% adds significant risk pressure. "
            f"Automation threatens {economic.automation_risk:.0f}% of related roles. "
            f"Economic strength at {economic.economic_score:.0f}/100 suggests "
            f"{'stable conditions' if economic_score > 0.6 else 'potential headwinds'}. "
            f"Overall risk level: {risk_level}. "
            f"Downside probability: {downside_prob:.0f}%, Failure probability: {failure_prob:.0f}%."
        )

        score_changes = {
            "base_risk": round(base_risk, 1),
            "final_risk": score,
            "unemployment_contribution": round(unemp_risk, 1),
            "automation_contribution": round(auto_risk, 1),
            "economic_volatility_contribution": round(economic_volatility, 1),
            "downside_probability": round(downside_prob, 1),
            "failure_probability": round(failure_prob, 1),
        }

        logger.info("[RiskAgent] score=%.1f base=%.1f unemp=%.1f auto=%.1f econ_vol=%.1f downside=%.1f%%",
                     score, base_risk, unemp_risk, auto_risk, economic_volatility, downside_prob)

        return AgentOutput(
            agent_name=self.name,
            score=score,
            confidence=round(70 + economic.data_confidence * 15, 1),
            reasoning=reasoning,
            evidence=evidence,
            assumptions=["Economic cycles follow historical patterns", "No black swan events modeled", "Risk compounds over time"],
            risks=[f"Timeline C has {failure_prob:.0f}% failure probability", "Career breaks are hard to recover from", "High stress correlates with health decline"],
            opportunities=["Timeline A provides stability buffer", "Timeline B offers balanced risk exposure"],
            recommendation="Timeline A for risk-averse; Timeline B with hedging for moderate risk; Timeline C only with strong safety net",
            impact="neutral" if score < 60 else "negative",
            year_scores=scores,
            score_changes=score_changes,
            data_used=data_used,
            impact_factors=impact_factors,
        )
