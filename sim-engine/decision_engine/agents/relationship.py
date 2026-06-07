from __future__ import annotations
import math
from typing import Any, Dict, List
from . import BaseAgent
from ..types import AgentOutput, UserProfile, EconomicData, FuturePath, DecisionOption, SIMULATION_YEARS


class RelationshipAgent(BaseAgent):
    name = "relationship"

    def analyze(self, decision: str, profile: UserProfile, economic: EconomicData, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> AgentOutput:
        per_option = {}
        for opt in options:
            path = future_paths.get(opt.title)
            if not path:
                per_option[opt.title] = 50.0
                continue
            rel_scores = []
            for yk in SIMULATION_YEARS:
                ys = path.years.get(yk)
                if ys:
                    combined = ys.relationships * 0.5 + ys.social_support * 0.3 + (100 - ys.stress * 0.3) * 0.2
                    rel_scores.append(combined)
            per_option[opt.title] = round(sum(rel_scores) / len(rel_scores), 1) if rel_scores else 50

        score = round(sum(per_option.values()) / len(per_option), 1) if per_option else 50
        option_rankings = sorted(per_option, key=per_option.get, reverse=True)

        relationship_modifiers = {
            "married": 10, "engaged": 8, "in_relationship": 5, "single": 0, "divorced": -5,
        }
        status_bonus = relationship_modifiers.get(profile.relationship_status, 0)
        children_impact = min(profile.children_count * 5, 15)
        score = min(100, score + status_bonus + children_impact)

        impact_factors = [
            {"factor": "Relationship Status", "value": profile.relationship_status, "delta": round(status_bonus, 1)},
            {"factor": "Children", "value": str(profile.children_count), "delta": round(children_impact, 1)},
            {"factor": "Relocation Risk", "value": f"{'High' if 'relocate' in decision.lower() or 'move' in decision.lower() else 'Low'}", "delta": round(-8 if any(w in decision.lower() for w in ['relocate','move','abroad','city']) else 0, 1)},
        ]

        evidence = [
            f"Best for relationships: {option_rankings[0]} ({per_option.get(option_rankings[0], 50):.0f}/100)",
            f"Status bonus: +{status_bonus:.0f}pts",
            f"Children impact: +{children_impact:.0f}pts",
        ]

        return AgentOutput(
            agent_name=self.name, score=round(score, 1), confidence=68,
            reasoning=f"Relationship analysis shows {option_rankings[0]} best preserves social connections. "
                      f"{'Current relationship provides stability bonus.' if status_bonus > 0 else 'Being single allows flexibility.'} "
                      f"{'Relocation may strain existing relationships.' if any(w in decision.lower() for w in ['relocate','move','abroad','city']) else ''}",
            evidence=evidence,
            assumptions=["Family support assumed stable", "Social connections require active maintenance", "Quality > quantity in relationships"],
            risks=["Ambitious career paths strain relationships", "Relocation risks social isolation", "Long hours correlate with relationship dissatisfaction"],
            opportunities=[f"{option_rankings[0]} preserves core relationships", "Balanced approach allows career + connection"],
            recommendation=f"Relationship-optimal path: {option_rankings[0]}",
            impact="positive" if score > 55 else "neutral",
            per_option_scores=per_option, option_rankings=option_rankings,
            tension_with=["career", "financial"],
            score_changes={"relationship_status_bonus": round(status_bonus, 1), "children_impact": round(children_impact, 1)},
            data_used=["relationship_status", "children_count", "relationships_score", "social_support"],
            impact_factors=impact_factors,
            verdict=f"{option_rankings[0]} best supports your relationships",
        )
