from __future__ import annotations
import math
import logging
from typing import Any, Dict, List
from . import BaseAgent
from ..types import AgentOutput, UserProfile, EconomicData, FuturePath, DecisionOption, SIMULATION_YEARS

logger = logging.getLogger(__name__)


class EconomicAgent(BaseAgent):
    name = "economic"

    def analyze(self, decision: str, profile: UserProfile, economic: EconomicData, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> AgentOutput:
        gdp = economic.gdp_growth / 100.0
        infl = economic.inflation_cpi / 100.0
        unemp = economic.unemployment_rate / 10.0
        ind_health = economic.industry_health / 100.0
        sal_growth = economic.salary_growth_pct / 100.0
        economic_score = economic.economic_score / 100.0
        employment_score = economic.employment_score / 100.0

        base_score = 50
        gdp_contrib = gdp * 30
        ind_contrib = ind_health * 25
        sal_contrib = sal_growth * 20
        unemp_penalty = unemp * 15
        infl_penalty = infl * 10
        economic_contrib = (economic_score - 0.5) * 15
        employment_contrib = (employment_score - 0.5) * 10

        score = base_score + gdp_contrib + ind_contrib + sal_contrib + economic_contrib + employment_contrib - unemp_penalty - infl_penalty
        score = round(min(100, max(0, score)), 1)

        per_option = {}
        for opt in options:
            per_option[opt.title] = round(min(100, score * (1 + opt.risk_level.count("high") * 0.1)), 1)

        option_rankings = sorted(per_option, key=per_option.get, reverse=True)

        scores = {}
        for idx, yk in enumerate(SIMULATION_YEARS):
            t = idx + 1
            year_mult = 1 + t * 0.05
            scores[yk] = round(min(100, score * year_mult), 1)

        impact_factors = [
            {"factor": "GDP Growth", "value": f"{economic.gdp_growth:.1f}%", "delta": round(gdp_contrib, 1)},
            {"factor": "Inflation", "value": f"{economic.inflation_cpi:.1f}%", "delta": round(-infl_penalty, 1)},
            {"factor": "Unemployment", "value": f"{economic.unemployment_rate:.1f}%", "delta": round(-unemp_penalty, 1)},
            {"factor": "Industry Health", "value": f"{economic.industry_health:.0f}/100", "delta": round(ind_contrib, 1)},
        ]

        evidence = [
            f"GDP contribution: +{gdp_contrib:.0f}pts",
            f"Inflation drag: -{infl_penalty:.0f}pts",
            f"Unemployment drag: -{unemp_penalty:.0f}pts",
            f"Industry health boost: +{ind_contrib:.0f}pts",
            f"Economic strength: {economic.economic_score:.0f}/100",
            f"Best option economically: {option_rankings[0] if option_rankings else 'N/A'}",
        ]

        data_used = ["gdp_growth", "inflation_cpi", "unemployment_rate", "industry_health", "salary_growth_pct", "economic_score", "employment_score"]

        macro_outlook = "strong" if gdp > 0.06 and infl < 0.06 else "mixed" if gdp > 0.03 else "weak"
        reasoning = (
            f"Macroeconomic analysis: GDP {economic.gdp_growth:.1f}% ({macro_outlook}), "
            f"inflation {economic.inflation_cpi:.1f}%, unemployment {economic.unemployment_rate:.1f}%. "
            f"Overall economic conditions {'support' if score > 55 else 'challenge'} your decision. "
            f"Best option in current climate: {option_rankings[0] if option_rankings else 'N/A'}."
        )

        return AgentOutput(
            agent_name=self.name, score=score, confidence=round(60 + economic.data_confidence * 35, 1),
            reasoning=reasoning, evidence=evidence,
            assumptions=["GDP growth remains in current range", "No global recession in 5-year window", "Industry trends persist"],
            risks=["Inflation could spike above 8%", "Industry disruption from AI/automation", "Geopolitical events could impact economy"],
            opportunities=["Current GDP trend supports strong job market", "Salary growth outpacing inflation"],
            recommendation="Economic conditions favor career investment now",
            impact="positive" if score > 55 else "neutral",
            per_option_scores=per_option, option_rankings=option_rankings,
            year_scores=scores,
            score_changes={"gdp_contribution": round(gdp_contrib, 1), "inflation_penalty": round(-infl_penalty, 1), "unemployment_penalty": round(-unemp_penalty, 1), "industry_contribution": round(ind_contrib, 1)},
            data_used=data_used, impact_factors=impact_factors,
            verdict="Economic climate supports this decision" if score > 55 else "Economic climate is challenging",
        )
