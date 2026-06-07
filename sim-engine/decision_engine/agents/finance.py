from __future__ import annotations
import math
import logging
from typing import Any, Dict
from . import BaseAgent
from ..types import AgentOutput, UserProfile, EconomicData, Timeline, YEARS

logger = logging.getLogger(__name__)


class FinanceAgent(BaseAgent):
    name = "finance"

    def analyze(self, decision: str, profile: UserProfile, economic: EconomicData, timelines: Dict[str, Timeline]) -> AgentOutput:
        scores = {}
        for yk in YEARS:
            tl_b = timelines.get("Timeline B", {}).years.get(yk)
            income = tl_b.income if tl_b else 50
            savings = tl_b.savings if tl_b else 0
            net_worth = tl_b.net_worth if tl_b else 0
            combined = income * 0.4 + min(savings * 2, 40) + min(net_worth * 0.3, 20)
            scores[yk] = round(min(100, combined), 1)

        base = scores.get("Year10", 50)

        inflation = economic.inflation_cpi / 100.0
        col_index = economic.cost_of_living_index
        salary_growth = economic.salary_growth_pct / 100.0
        economic_score = economic.economic_score / 100.0
        col_score = economic.cost_of_living_score / 100.0

        real_salary_growth = max(0, salary_growth - inflation)
        purchasing_power_erosion = max(0, (inflation - salary_growth) * 100)
        col_penalty = max(0, (col_index - 1.0) * 20)

        inflation_penalty = max(0, economic.inflation_cpi - 4) * 2
        col_penalty_scored = col_penalty * 0.5

        score = base - inflation_penalty - col_penalty_scored
        score = round(max(0, score), 1)

        data_used = ["inflation_cpi", "cost_of_living_index", "salary_growth_pct", "economic_score"]

        impact_factors = [
            {"factor": "Inflation", "value": f"{economic.inflation_cpi:.1f}%", "delta": round(-inflation_penalty, 1)},
            {"factor": "Cost of Living", "value": f"{col_index:.1f}x", "delta": round(-col_penalty_scored, 1)},
            {"factor": "Real Salary Growth", "value": f"{real_salary_growth*100:.1f}%", "delta": round(real_salary_growth * 20, 1)},
            {"factor": "Economic Strength", "value": f"{economic.economic_score:.0f}/100", "delta": round((economic_score - 0.5) * 15, 1)},
        ]

        real_salary_lpa = 10 * (1 + real_salary_growth)
        purchasing_power = real_salary_lpa / col_index

        evidence = [
            f"Inflation: {economic.inflation_cpi:.1f}% (penalty: -{inflation_penalty:.0f}pts)",
            f"Cost of living index: {col_index:.1f}x (penalty: -{col_penalty_scored:.0f}pts)",
            f"Real salary growth (after inflation): {real_salary_growth*100:.1f}%",
            f"Projected Year10 income: {scores.get('Year10', 50):.0f}/100",
            f"Real salary value: ₹{real_salary_lpa:.1f} LPA in purchasing power",
        ]

        if economic.data_freshness.get("cost_of_living") == "live":
            data_used.append("live_cost_of_living")
            evidence.append("Using live cost-of-living data from Numbeo")

        reasoning = (
            f"Financial projection driven by inflation ({economic.inflation_cpi:.1f}%) and "
            f"cost of living ({col_index:.1f}x index). Real salary growth after inflation is "
            f"{real_salary_growth*100:.1f}%. "
            f"{'Inflation is eroding purchasing power significantly.' if inflation_penalty > 10 else 'Inflation impact is manageable.'} "
            f"{'High cost of living in this location reduces effective savings.' if col_index > 1.3 else 'Cost of living is reasonable for this location.'}"
        )

        score_changes = {
            "base_score": round(base, 1),
            "final_score": score,
            "inflation_penalty": round(inflation_penalty, 1),
            "col_penalty": round(col_penalty_scored, 1),
            "real_salary_growth": round(real_salary_growth * 100, 1),
            "purchasing_power_lpa": round(purchasing_power, 1),
        }

        logger.info("[FinanceAgent] score=%.1f base=%.1f infl_pen=%.1f col_pen=%.1f real_sal=%.1f%%",
                     score, base, inflation_penalty, col_penalty_scored, real_salary_growth * 100)

        return AgentOutput(
            agent_name=self.name,
            score=score,
            confidence=round(65 + economic.data_confidence * 30, 1),
            reasoning=reasoning,
            evidence=evidence,
            assumptions=["Inflation stays near current levels", "Interest rates remain stable", "No major market crashes"],
            risks=["High inflation erodes purchasing power", "Cost of living may outpace salary growth", "Market downturn could reduce savings"],
            opportunities=["Compound interest accelerates after Year 5", "Real estate or equity investments"],
            recommendation="Timeline B offers the best risk-adjusted financial outcome",
            impact="positive" if score > 55 else "neutral",
            year_scores=scores,
            score_changes=score_changes,
            data_used=data_used,
            impact_factors=impact_factors,
        )
