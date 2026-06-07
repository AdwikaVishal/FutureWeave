from __future__ import annotations
from typing import Any, Dict, List
from . import BaseAgent
from ..types import AgentOutput, UserProfile, EconomicData, FuturePath, DecisionOption, SIMULATION_YEARS


class TimeAgent(BaseAgent):
    name = "time"

    def analyze(self, decision: str, profile: UserProfile, economic: EconomicData, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> AgentOutput:
        per_option = {}
        for opt in options:
            path = future_paths.get(opt.title)
            if not path:
                per_option[opt.title] = 50.0
                continue
            opportunity_cost = 0
            for yk in SIMULATION_YEARS:
                ys = path.years.get(yk)
                if ys:
                    opportunity_cost += (100 - ys.income) * 0.15 + (100 - ys.career_growth) * 0.15 + ys.regret * 0.2
            per_option[opt.title] = round(max(0, 100 - opportunity_cost / len(SIMULATION_YEARS)), 1)

        option_rankings = sorted(per_option, key=per_option.get, reverse=True)
        best = option_rankings[0] if option_rankings else "Unknown"

        age_urgency = max(0, (profile.age - 25) / 40 * 15)
        time_horizon_score = min(profile.years_experience * 2, 15)

        score = round(per_option.get(best, 50) + time_horizon_score - age_urgency, 1)
        score = max(0, min(100, score))

        impact_factors = [
            {"factor": "Age Urgency", "value": f"{profile.age}yrs", "delta": round(-age_urgency, 1)},
            {"factor": "Experience Leverage", "value": f"{profile.years_experience}yrs", "delta": round(time_horizon_score, 1)},
            {"factor": "Opportunity Cost", "value": best, "delta": round(-(100 - per_option.get(best, 50)), 1)},
        ]

        evidence = [
            f"Best use of time: {best} ({per_option.get(best, 50):.0f}/100)",
            f"Age urgency: -{age_urgency:.0f}pts",
            f"Experience leverage: +{time_horizon_score:.0f}pts",
            f"Years invested compounds with experience",
        ]

        return AgentOutput(
            agent_name=self.name, score=round(score, 1), confidence=65,
            reasoning=f"Time analysis for {decision}. At age {profile.age}, time horizon is "
                      f"{'limited — decisions now compound significantly' if age_urgency > 5 else 'long — compounding will work in your favor'}. "
                      f"Best time investment: {best}. Opportunity cost of suboptimal paths is meaningful.",
            evidence=evidence,
            assumptions=["Time invested compounds similar to compound interest", "Early career years are highest leverage", "Regret minimization is a valid strategy"],
            risks=["Wasting years in wrong path is irrecoverable", "Delaying decisions limits future optionality", "Time horizon shrinks with age"],
            opportunities=["Early career years offer highest compounding returns", f"Experience leverage at {profile.years_experience}yrs is growing"],
            recommendation=f"Best time investment: {best}",
            impact="positive" if score > 55 else "neutral",
            per_option_scores=per_option, option_rankings=option_rankings,
            tension_with=["risk", "financial"],
            score_changes={"age_urgency": round(age_urgency, 1), "experience_leverage": round(time_horizon_score, 1)},
            data_used=["age", "years_experience", "income", "career_growth", "regret_score"],
            impact_factors=impact_factors,
            verdict=f"{best} makes best use of your time",
        )
