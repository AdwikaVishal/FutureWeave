from __future__ import annotations
import math
import logging
from typing import Any, Dict, List
from . import BaseAgent
from ..types import AgentOutput, UserProfile, EconomicData, FuturePath, DecisionOption, SIMULATION_YEARS

logger = logging.getLogger(__name__)


class RiskAgent(BaseAgent):
    name = "risk"

    def analyze(self, decision: str, profile: UserProfile, economic: EconomicData, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> AgentOutput:
        per_option = {}
        for opt in options:
            path = future_paths.get(opt.title)
            if not path:
                per_option[opt.title] = 50.0
                continue
            y10 = path.years.get("Year10", path.years.get("Year5"))
            risk_val = 100 - (y10.health if y10 else 50) * 0.4 + (y10.stress if y10 else 50) * 0.3 + y10.risk_exposure * 0.3
            per_option[opt.title] = round(min(100, risk_val), 1)

        base_risk = per_option.get(list(per_option.keys())[0], 50)
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
        debt_risk = min(profile.debt_amount / 100000 * 2, 10)
        age_risk = max(0, (profile.age - 35) * 0.5)

        combined_risk = base_risk + unemp_risk + auto_risk + economic_volatility + industry_volatility - employment_risk * 0.5 + debt_risk + age_risk
        score = round(min(100, combined_risk), 1)

        downside_prob = min(100, unemp_risk + auto_risk + max(0, (100 - economic_score * 100) * 0.3) + debt_risk)
        failure_prob = min(100, base_risk * 0.3 + unemp_risk * 0.4 + auto_risk * 0.3)

        option_rankings = sorted(per_option, key=per_option.get)
        safest = option_rankings[0] if option_rankings else "Unknown"

        impact_factors = [
            {"factor": "Unemployment Risk", "value": f"{economic.unemployment_rate:.1f}%", "delta": round(unemp_risk, 1)},
            {"factor": "Automation Risk", "value": f"{economic.automation_risk:.0f}%", "delta": round(auto_risk, 1)},
            {"factor": "Economic Volatility", "value": f"{economic.economic_score:.0f}/100", "delta": round(economic_volatility, 1)},
            {"factor": "Industry Volatility", "value": f"{economic.industry_score:.0f}/100", "delta": round(industry_volatility, 1)},
            {"factor": "Debt Risk", "value": f"₹{profile.debt_amount:.0f}", "delta": round(debt_risk, 1)},
        ]

        evidence = [
            f"Unemployment: {economic.unemployment_rate:.1f}% (+{unemp_risk:.0f}pts risk)",
            f"Automation risk: {economic.automation_risk:.0f}% (+{auto_risk:.0f}pts risk)",
            f"Downside probability: {downside_prob:.0f}%", f"Failure probability: {failure_prob:.0f}%",
            f"Safest option: {safest}", f"Debt amplifies risk by +{debt_risk:.0f}pts",
        ]

        data_used = ["unemployment_rate", "automation_risk", "economic_score", "employment_score", "industry_score", "debt_amount"]

        risk_level = "elevated" if score > 65 else "moderate" if score > 45 else "low"
        reasoning = (
            f"Risk assessment for {decision}. Unemployment at {economic.unemployment_rate:.1f}% "
            f"and automation at {economic.automation_risk:.0f}% create meaningful risk pressure. "
            f"Overall risk level: {risk_level}. Downside probability: {downside_prob:.0f}%. "
            f"Safest path: {safest}. "
            f"{'High debt amplifies financial vulnerability.' if debt_risk > 5 else 'Debt risk is manageable.'}"
        )

        return AgentOutput(
            agent_name=self.name, score=score, confidence=round(70 + economic.data_confidence * 15, 1),
            reasoning=reasoning, evidence=evidence,
            assumptions=["Economic cycles follow historical patterns", "No black swan events modeled", "Risk compounds over time"],
            risks=[f"{safest} has {failure_prob:.0f}% failure probability", "Career breaks are hard to recover from", "High stress correlates with health decline"],
            opportunities=[f"{option_rankings[-1] if len(option_rankings) > 1 else safest} offers highest upside but requires strong safety net"],
            recommendation=f"Lowest risk option: {safest}",
            impact="neutral" if score < 60 else "negative",
            per_option_scores=per_option, option_rankings=option_rankings,
            tension_with=["opportunity", "identity"],
            score_changes={"base_risk": round(base_risk, 1), "final_risk": score, "downside_probability": round(downside_prob, 1), "failure_probability": round(failure_prob, 1)},
            data_used=data_used, impact_factors=impact_factors,
            verdict=f"{safest} minimises downside risk",
        )
