from __future__ import annotations
import math
import logging
from typing import Any, Dict, List
from . import BaseAgent
from ..types import AgentOutput, UserProfile, EconomicData, FuturePath, DecisionOption, SIMULATION_YEARS

logger = logging.getLogger(__name__)


class StrategicAgent(BaseAgent):
    name = "strategic"

    def analyze(self, decision: str, profile: UserProfile, economic: EconomicData, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> AgentOutput:
        per_option = {}
        for opt in options:
            path = future_paths.get(opt.title)
            if not path:
                per_option[opt.title] = 50.0
                continue
            y10 = path.years.get("Year10", path.years.get("Year5"))
            y20 = path.years.get("Year20")
            if y20 and y10:
                momentum = (y20.career_growth + y20.income) - (y10.career_growth + y10.income)
            else:
                momentum = 0
            strategic_score = (
                (y10.career_growth if y10 else 50) * 0.25 +
                (y10.opportunity if y10 else 50) * 0.25 +
                max(0, momentum) * 0.2 +
                (y10.learning_growth if y10 else 50) * 0.2 +
                (y10.freedom if y10 else 50) * 0.1
            )
            per_option[opt.title] = round(min(100, strategic_score), 1)

        option_rankings = sorted(per_option, key=per_option.get, reverse=True)
        best = option_rankings[0] if option_rankings else "Unknown"
        score = round(per_option.get(best, 50), 1)

        market_timing = (economic.economic_score / 100.0) * 10
        skill_leverage = min(profile.years_experience * 1.5, 10)
        industry_tailwind = (economic.industry_score / 100.0) * 10

        score = min(100, score + market_timing + skill_leverage + industry_tailwind)

        impact_factors = [
            {"factor": "Market Timing", "value": f"{economic.economic_score:.0f}/100", "delta": round(market_timing, 1)},
            {"factor": "Skill Leverage", "value": f"{profile.years_experience}yrs exp", "delta": round(skill_leverage, 1)},
            {"factor": "Industry Tailwind", "value": f"{economic.industry_score:.0f}/100", "delta": round(industry_tailwind, 1)},
            {"factor": "Career Momentum", "value": best, "delta": round(per_option.get(best, 50) * 0.15, 1)},
        ]

        evidence = [
            f"Strategically optimal: {best} ({per_option.get(best, 50):.0f}/100)",
            f"Market tailwind: +{market_timing:.0f}pts",
            f"Skill leverage at {profile.years_experience}yrs: +{skill_leverage:.0f}pts",
            f"Industry tailwind: +{industry_tailwind:.0f}pts",
        ]

        return AgentOutput(
            agent_name=self.name, score=round(score, 1), confidence=75,
            reasoning=f"Strategic analysis for {decision}. Long-term optimal path: {best}. "
                      f"Market conditions ({economic.economic_score:.0f}/100) {'favor' if market_timing > 5 else 'caution'} bold moves. "
                      f"Your skill set at {profile.years_experience} years experience is at "
                      f"{'peak leverage' if skill_leverage > 7 else 'growing leverage'} point. "
                      f"Strategic recommendation: {best} for long-term compound advantage.",
            evidence=evidence,
            assumptions=["Long-term thinking beats short-term optimization", "Career capital compounds", "Strategic patience pays off"],
            risks=["Short-term thinking leads to suboptimal長期 results", "Timing the market is difficult", "Over-optimization causes paralysis"],
            opportunities=[f"{best} offers highest long-term compound growth", "Strategic positioning now pays for decades"],
            recommendation=f"Strategically optimal: {best}",
            impact="positive" if score > 55 else "neutral",
            per_option_scores=per_option, option_rankings=option_rankings,
            tension_with=["risk"],
            score_changes={"market_timing": round(market_timing, 1), "skill_leverage": round(skill_leverage, 1), "industry_tailwind": round(industry_tailwind, 1)},
            data_used=["economic_score", "industry_score", "years_experience", "career_growth", "opportunity", "learning_growth", "freedom"],
            impact_factors=impact_factors,
            verdict=f"{best} gives the best long-term strategic position",
        )
