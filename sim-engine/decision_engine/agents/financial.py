from __future__ import annotations
import math
import logging
from typing import Any, Dict, List
from . import BaseAgent
from ..types import AgentOutput, UserProfile, EconomicData, FuturePath, DecisionOption, SIMULATION_YEARS

logger = logging.getLogger(__name__)


class FinancialAgent(BaseAgent):
    name = "financial"

    def analyze(self, decision: str, profile: UserProfile, economic: EconomicData, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> AgentOutput:
        per_option = {}
        for opt in options:
            path = future_paths.get(opt.title)
            if not path:
                per_option[opt.title] = 50.0
                continue
            y10 = path.years.get("Year10", path.years.get("Year5"))
            income = y10.income if y10 else 50
            savings = y10.savings if y10 else 0
            net_worth = y10.net_worth if y10 else 0
            per_option[opt.title] = min(100, income * 0.3 + min(savings, 30) + min(net_worth * 0.2, 20) + 20)

        banking = per_option.get("Stay in Corporate", per_option.get(list(per_option.keys())[0], 50))
        equity = per_option.get("Join Startup", banking - 15) if "Join Startup" in per_option else banking - 10
        founder = per_option.get("Start Company", banking - 25) if "Start Company" in per_option else banking - 15

        inflation = economic.inflation_cpi / 100.0
        col_index = economic.cost_of_living_index
        salary_growth = economic.salary_growth_pct / 100.0
        economic_score = economic.economic_score / 100.0

        real_salary_growth = max(0, salary_growth - inflation)
        purchasing_power_erosion = max(0, (inflation - salary_growth) * 100)
        col_penalty = max(0, (col_index - 1.0) * 20)
        inflation_penalty = max(0, economic.inflation_cpi - 4) * 2
        col_penalty_scored = col_penalty * 0.5

        score = banking - inflation_penalty - col_penalty_scored
        score = round(max(0, score), 1)

        real_salary_lpa = (profile.current_salary or 10) * (1 + real_salary_growth)
        purchasing_power = real_salary_lpa / col_index

        option_rankings = sorted(per_option, key=per_option.get, reverse=True)

        impact_factors = [
            {"factor": "Inflation", "value": f"{economic.inflation_cpi:.1f}%", "delta": round(-inflation_penalty, 1)},
            {"factor": "Cost of Living", "value": f"{col_index:.1f}x", "delta": round(-col_penalty_scored, 1)},
            {"factor": "Real Salary Growth", "value": f"{real_salary_growth*100:.1f}%", "delta": round(real_salary_growth * 20, 1)},
            {"factor": "Economic Strength", "value": f"{economic.economic_score:.0f}/100", "delta": round((economic_score - 0.5) * 15, 1)},
            {"factor": "Savings Rate", "value": f"{profile.monthly_savings:.0f}/mo", "delta": round(min(profile.monthly_savings / 1000 * 5, 10), 1)},
            {"factor": "Debt Burden", "value": f"₹{profile.debt_amount:.0f}", "delta": round(-min(profile.debt_amount / 100000 * 3, 15), 1)},
        ]

        evidence = [
            f"Inflation: {economic.inflation_cpi:.1f}% (penalty: -{inflation_penalty:.0f}pts)",
            f"Cost of living index: {col_index:.1f}x (penalty: -{col_penalty_scored:.0f}pts)",
            f"Real salary growth (after inflation): {real_salary_growth*100:.1f}%",
            f"Current savings: ₹{profile.savings:.0f}, Monthly: ₹{profile.monthly_savings:.0f}",
            f"Debt: ₹{profile.debt_amount:.0f}",
            f"Best financial option: {option_rankings[0]}",
        ]
        if economic.data_freshness.get("cost_of_living") == "live":
            evidence.append("Using live cost-of-living data from Numbeo")

        data_used = ["inflation_cpi", "cost_of_living_index", "salary_growth_pct", "economic_score", "savings", "debt_amount"]

        reasoning = (
            f"Financial analysis for {decision}. Inflation at {economic.inflation_cpi:.1f}% "
            f"{'erodes' if inflation_penalty > 10 else 'moderately impacts'} purchasing power. "
            f"Real salary growth after inflation: {real_salary_growth*100:.1f}%. "
            f"Best option financially: {option_rankings[0]} with score {per_option.get(option_rankings[0], 50):.0f}/100. "
            f"{'Debt is a significant concern.' if profile.debt_amount > 500000 else 'Debt level is manageable.'}"
        )

        return AgentOutput(
            agent_name=self.name, score=score, confidence=round(65 + economic.data_confidence * 30, 1),
            reasoning=reasoning, evidence=evidence,
            assumptions=["Inflation stays near current levels", "Interest rates remain stable", "No major market crashes"],
            risks=[f"High inflation erodes purchasing power: -{inflation_penalty:.0f}pts", "Cost of living may outpace salary growth", "Market downturn could reduce savings"],
            opportunities=["Compound interest accelerates after Year 5", "Real estate or equity investments"],
            recommendation=f"Financially, {option_rankings[0]} offers the strongest outcome",
            impact="positive" if score > 55 else "neutral",
            per_option_scores=per_option, option_rankings=option_rankings,
            tension_with=["opportunity", "identity"],
            score_changes={"inflation_penalty": round(inflation_penalty, 1), "col_penalty": round(col_penalty_scored, 1), "real_salary_growth": round(real_salary_growth * 100, 1), "purchasing_power_lpa": round(purchasing_power, 1)},
            data_used=data_used, impact_factors=impact_factors,
            verdict=f"{option_rankings[0]} maximises financial security",
        )
