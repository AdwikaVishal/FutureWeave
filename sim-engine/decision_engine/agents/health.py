from __future__ import annotations
from typing import Any, Dict, List
from . import BaseAgent
from ..types import AgentOutput, UserProfile, EconomicData, FuturePath, DecisionOption, SIMULATION_YEARS


class HealthAgent(BaseAgent):
    name = "health"

    def analyze(self, decision: str, profile: UserProfile, economic: EconomicData, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> AgentOutput:
        per_option = {}
        for opt in options:
            path = future_paths.get(opt.title)
            if not path:
                per_option[opt.title] = 50.0
                continue
            health_scores = []
            for yk in SIMULATION_YEARS:
                ys = path.years.get(yk)
                if ys:
                    combined = ys.health * 0.5 + (100 - ys.stress) * 0.3 + (100 - ys.burnout_risk) * 0.2
                    health_scores.append(combined)
            per_option[opt.title] = round(sum(health_scores) / len(health_scores), 1) if health_scores else 50

        scores_list = list(per_option.values())
        score = round(sum(scores_list) / len(scores_list), 1) if scores_list else 50
        option_rankings = sorted(per_option, key=per_option.get, reverse=True)

        age_factor = max(0, (profile.age - 25) * 0.5)
        health_condition_penalty = {"poor": 15, "fair": 8, "good": 2, "excellent": 0}.get(profile.health_condition, 2)
        score = max(0, score - age_factor - health_condition_penalty)

        impact_factors = [
            {"factor": "Age Factor", "value": f"{profile.age}yrs", "delta": round(-age_factor, 1)},
            {"factor": "Health Condition", "value": profile.health_condition, "delta": round(-health_condition_penalty, 1)},
            {"factor": "Stress Impact", "value": "Across paths", "delta": round(-min(score * 0.1, 10), 1)},
        ]

        evidence = [
            f"Best for health: {option_rankings[0]} ({per_option.get(option_rankings[0], 50):.0f}/100)",
            f"Age adjustment: -{age_factor:.0f}pts",
            f"Health condition penalty: -{health_condition_penalty:.0f}pts",
            f"Health status: {profile.health_condition}",
        ]

        return AgentOutput(
            agent_name=self.name, score=round(score, 1), confidence=70,
            reasoning=f"Health analysis across all paths. Best option for health: {option_rankings[0]}. Age and current health condition significantly impact long-term health outcomes. Stress accumulation is the primary health risk.",
            evidence=evidence,
            assumptions=["Regular health checkups assumed", "Work stress manageable with good habits", "Health baseline stable"],
            risks=["Burnout risk in high-growth paths", "Sedentary lifestyle effects in desk jobs", "Stress compounds over decades"],
            opportunities=[f"{option_rankings[0]} offers best health-work balance", "Better healthcare access over time"],
            recommendation=f"Health-optimal path: {option_rankings[0]}",
            impact="positive" if score > 55 else "neutral",
            per_option_scores=per_option, option_rankings=option_rankings,
            tension_with=["career", "financial"],
            score_changes={"age_penalty": round(age_factor, 1), "health_penalty": round(health_condition_penalty, 1)},
            data_used=["age", "health_condition", "stress", "burnout_risk"],
            impact_factors=impact_factors,
            verdict=f"{option_rankings[0]} preserves health best long-term",
        )
