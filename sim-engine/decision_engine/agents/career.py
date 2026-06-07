from __future__ import annotations
import math
import logging
from typing import Any, Dict, List
from . import BaseAgent
from ..types import AgentOutput, UserProfile, EconomicData, FuturePath, DecisionOption, SIMULATION_YEARS

logger = logging.getLogger(__name__)


class CareerAgent(BaseAgent):
    name = "career"

    def analyze(self, decision: str, profile: UserProfile, economic: EconomicData, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> AgentOutput:
        per_option = {}
        for opt in options:
            path = future_paths.get(opt.title)
            if not path:
                per_option[opt.title] = 50.0
                continue
            career_scores = []
            for yk in SIMULATION_YEARS:
                ys = path.years.get(yk)
                if ys:
                    combined = ys.career_growth * 0.4 + ys.income * 0.3 + ys.learning_growth * 0.2 + ys.opportunity * 0.1
                    career_scores.append(combined)
            per_option[opt.title] = round(sum(career_scores) / len(career_scores), 1) if career_scores else 50

        base_score = max(per_option.values()) if per_option else 50
        sal_growth = economic.salary_growth_pct / 100.0
        ind_health = economic.industry_health / 100.0
        salary_score = economic.salary_score / 100.0
        industry_score = economic.industry_score / 100.0
        employment_score = economic.employment_score / 100.0
        col_index = economic.cost_of_living_index

        demand_factor = ind_health * 0.3 + industry_score * 0.25 + salary_score * 0.25 + employment_score * 0.2
        col_penalty = max(0, (col_index - 1.0) * 5)
        exp_bonus = min(profile.years_experience * 1.5, 10)

        score = base_score * (0.3 + 0.4 * demand_factor + 0.2 * (1 + sal_growth) + 0.1 * employment_score) - col_penalty + exp_bonus
        score = round(min(100, score), 1)

        option_rankings = sorted(per_option, key=per_option.get, reverse=True)
        best = option_rankings[0] if option_rankings else "Unknown"
        demand_direction = "growing" if demand_factor > 0.55 else "stable" if demand_factor > 0.4 else "declining"
        salary_direction = "outpacing inflation" if sal_growth > economic.inflation_cpi / 100.0 else "below inflation"

        impact_factors = [
            {"factor": "Salary Growth", "value": f"+{economic.salary_growth_pct:.1f}%", "delta": round(sal_growth * 25, 1)},
            {"factor": "Industry Demand", "value": f"{economic.industry_health:.0f}/100", "delta": round((ind_health - 0.5) * 20, 1)},
            {"factor": "Experience Premium", "value": f"{profile.years_experience}yrs", "delta": round(exp_bonus, 1)},
            {"factor": "Cost of Living", "value": f"{col_index:.1f}x", "delta": round(-col_penalty, 1)},
        ]

        evidence = [
            f"Salary growth: {economic.salary_growth_pct:.1f}% ({salary_direction})",
            f"Industry health: {economic.industry_health:.0f}/100 ({demand_direction} demand)",
            f"Experience leverage: +{exp_bonus:.0f}pts at {profile.years_experience}yrs",
            f"Best career path: {best} ({per_option.get(best, 50):.0f}/100)",
        ]

        data_used = ["salary_growth_pct", "industry_health", "employment_score", "salary_score", "years_experience"]

        reasoning = (
            f"Career projection for {decision}. Industry demand is {demand_direction} "
            f"(health: {economic.industry_health:.0f}/100). Salary growth at {economic.salary_growth_pct:.1f}% "
            f"is {salary_direction}. Experience at {profile.years_experience} years provides "
            f"{'strong' if exp_bonus > 7 else 'growing'} leverage. Best career path: {best}."
        )

        return AgentOutput(
            agent_name=self.name, score=score, confidence=round(65 + ind_health * 25, 1),
            reasoning=reasoning, evidence=evidence,
            assumptions=["Career growth correlates with industry demand", "Skills compound over time", "Experience premium grows with expertise"],
            risks=[f"Industry disruption ({economic.automation_risk:.0f}% automation risk)", "Stagnation without continuous learning"],
            opportunities=[f"Leadership track in {demand_direction} market", f"{best} offers best career trajectory"],
            recommendation=f"Best career path: {best}",
            impact="positive" if score > 60 else "neutral",
            per_option_scores=per_option, option_rankings=option_rankings,
            tension_with=["health", "relationship"],
            score_changes={"base_score": round(base_score, 1), "final_score": score, "demand_factor": round(demand_factor, 3), "experience_bonus": round(exp_bonus, 1)},
            data_used=data_used, impact_factors=impact_factors,
            verdict=f"{best} accelerates your career most",
        )
