from __future__ import annotations
from typing import Any, Dict, List
from . import BaseAgent
from ..types import AgentOutput, UserProfile, EconomicData, FuturePath, DecisionOption, SIMULATION_YEARS


class LifestyleAgent(BaseAgent):
    name = "lifestyle"

    def analyze(self, decision: str, profile: UserProfile, economic: EconomicData, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> AgentOutput:
        per_option = {}
        for opt in options:
            path = future_paths.get(opt.title)
            if not path:
                per_option[opt.title] = 50.0
                continue
            life_scores = []
            for yk in SIMULATION_YEARS:
                ys = path.years.get(yk)
                if ys:
                    combined = (100 - ys.stress) * 0.25 + ys.happiness * 0.25 + ys.freedom * 0.2 + ys.health * 0.15 + (100 - ys.burnout_risk) * 0.15
                    life_scores.append(combined)
            per_option[opt.title] = round(sum(life_scores) / len(life_scores), 1) if life_scores else 50

        option_rankings = sorted(per_option, key=per_option.get, reverse=True)
        best = option_rankings[0] if option_rankings else "Unknown"
        score = round(per_option.get(best, 50), 1)

        col_score = economic.cost_of_living_score / 100.0
        location_quality = col_score * 10
        score = min(100, score + location_quality)

        impact_factors = [
            {"factor": "Stress Level", "value": f"{'Low' if score > 60 else 'Moderate' if score > 40 else 'High'}", "delta": round(-(100 - score) * 0.2, 1)},
            {"factor": "Location Quality", "value": f"{economic.cost_of_living_score:.0f}/100", "delta": round(location_quality, 1)},
            {"factor": "Work-Life Balance", "value": best, "delta": round(per_option.get(best, 50) * 0.15, 1)},
        ]

        evidence = [
            f"Best lifestyle: {best} ({per_option.get(best, 50):.0f}/100)",
            f"Location quality bonus: +{location_quality:.0f}pts",
            f"Stress optimized across all paths",
        ]

        return AgentOutput(
            agent_name=self.name, score=round(score, 1), confidence=66,
            reasoning=f"Lifestyle quality assessment. {best} offers the best overall lifestyle. "
                      f"Focus on low stress, high happiness, and personal freedom. "
                      f"Location quality at {economic.cost_of_living_score:.0f}/100 "
                      f"{'enhances' if location_quality > 5 else 'limits'} lifestyle options.",
            evidence=evidence,
            assumptions=["Lifestyle preferences are individual", "Financial comfort improves lifestyle quality", "Stress management skills vary"],
            risks=["High-stress paths lead to burnout by Year 5-7", "Career-focused lifestyles may lack fulfillment"],
            opportunities=[f"{best} offers best lifestyle compromise", "Financial success enables lifestyle choices later"],
            recommendation=f"Best lifestyle path: {best}",
            impact="positive" if score > 55 else "neutral",
            per_option_scores=per_option, option_rankings=option_rankings,
            tension_with=["career", "financial"],
            score_changes={"location_quality": round(location_quality, 1)},
            data_used=["stress", "happiness", "freedom", "health", "burnout_risk", "cost_of_living_score"],
            impact_factors=impact_factors,
            verdict=f"{best} offers the best everyday life quality",
        )
