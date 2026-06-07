from __future__ import annotations
import math
import logging
from typing import Any, Dict, List
from . import BaseAgent
from ..types import AgentOutput, UserProfile, EconomicData, FuturePath, DecisionOption, SIMULATION_YEARS

logger = logging.getLogger(__name__)


class OpportunityAgent(BaseAgent):
    name = "opportunity"

    def analyze(self, decision: str, profile: UserProfile, economic: EconomicData, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> AgentOutput:
        per_option = {}
        for opt in options:
            path = future_paths.get(opt.title)
            if not path:
                per_option[opt.title] = 50.0
                continue
            best_opp = 0
            for yk in SIMULATION_YEARS:
                ys = path.years.get(yk)
                if ys:
                    best_opp = max(best_opp, ys.opportunity)
            per_option[opt.title] = round(min(100, best_opp * 0.6 + 40), 1)

        base = max(per_option.values()) if per_option else 50
        industry_score = economic.industry_score / 100.0
        employment_score = economic.employment_score / 100.0
        salary_score = economic.salary_score / 100.0
        economic_score = economic.economic_score / 100.0
        ind_health = economic.industry_health / 100.0

        industry_opportunity = industry_score * 30
        employment_opportunity = employment_score * 25
        salary_opportunity = salary_score * 20
        gdp_opportunity = economic_score * 15
        risk_premium = profile.risk_tolerance * 15
        network_effect = min(profile.years_experience * 2, 10)

        opportunity_boost = (industry_opportunity + employment_opportunity + salary_opportunity + gdp_opportunity + network_effect) / 100.0
        score = base * (0.4 + 0.6 * opportunity_boost) + risk_premium
        score = round(min(100, score), 1)

        option_rankings = sorted(per_option, key=per_option.get, reverse=True)
        best_option = option_rankings[0] if option_rankings else "Unknown"

        impact_factors = [
            {"factor": "Industry Growth", "value": f"{economic.industry_score:.0f}/100", "delta": round(industry_opportunity * 0.3, 1)},
            {"factor": "Job Market Demand", "value": f"{economic.employment_score:.0f}/100", "delta": round(employment_opportunity * 0.3, 1)},
            {"factor": "Salary Growth Potential", "value": f"{economic.salary_growth_pct:.1f}%", "delta": round(salary_opportunity * 0.25, 1)},
            {"factor": "Network Effect", "value": f"{profile.years_experience}y exp", "delta": round(network_effect, 1)},
            {"factor": "Risk Premium", "value": f"{profile.risk_tolerance:.2f} tol", "delta": round(risk_premium, 1)},
        ]

        evidence = [
            f"Industry growth: {economic.industry_score:.0f}/100",
            f"Employment market: {economic.employment_score:.0f}/100",
            f"Salary opportunity: {economic.salary_score:.0f}/100",
            f"Highest opportunity option: {best_option} ({per_option.get(best_option, 50):.0f}/100)",
            f"Risk tolerance amplifies opportunity capture by +{risk_premium:.0f}pts",
        ]

        data_used = ["industry_score", "employment_score", "salary_score", "economic_score", "industry_health", "risk_tolerance", "years_experience"]

        opp_level = "high" if score > 65 else "moderate" if score > 45 else "limited"
        reasoning = (
            f"Opportunity assessment for {decision}. Industry growth ({economic.industry_score:.0f}/100) "
            f"creates a {opp_level}-opportunity environment. "
            f"Best option for opportunity: {best_option}. "
            f"{'Your experience amplifies network effects.' if network_effect > 5 else 'Early career offers high growth potential.'}"
        )

        return AgentOutput(
            agent_name=self.name, score=score, confidence=round(68 + economic.data_confidence * 20, 1),
            reasoning=reasoning, evidence=evidence,
            assumptions=["Opportunities scale with career growth", "Network effects compound over time", "Better opportunities require proactive pursuit"],
            risks=["Opportunity cost of safe paths: -15-20%", "Missed timing windows can't be recovered"],
            opportunities=[f"High-growth industry ({economic.industry_health:.0f}% health) amplifies career optionality", "Year 5-10 inflection point for exponential opportunities"],
            recommendation=f"For maximum opportunity: {best_option}",
            impact="positive" if score > 60 else "neutral",
            per_option_scores=per_option, option_rankings=option_rankings,
            tension_with=["risk", "financial"],
            score_changes={"base_opportunity": round(base, 1), "final_opportunity": score, "industry_boost": round(industry_opportunity * 0.3, 1), "network_effect": round(network_effect, 1)},
            data_used=data_used, impact_factors=impact_factors,
            verdict=f"{best_option} maximises future optionality",
        )
