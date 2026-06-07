from __future__ import annotations
from typing import Any, Dict, List
from . import BaseAgent
from ..types import AgentOutput, UserProfile, EconomicData, FuturePath, DecisionOption, SIMULATION_YEARS


class HappinessAgent(BaseAgent):
    name = "happiness"

    def analyze(self, decision: str, profile: UserProfile, economic: EconomicData, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> AgentOutput:
        per_option = {}
        for opt in options:
            path = future_paths.get(opt.title)
            if not path:
                per_option[opt.title] = 50.0
                continue
            happy_scores = []
            for yk in SIMULATION_YEARS:
                ys = path.years.get(yk)
                if ys:
                    combined = ys.happiness * 0.4 + ys.purpose * 0.3 + (100 - ys.regret) * 0.2 + ys.learning_growth * 0.1
                    happy_scores.append(combined)
            per_option[opt.title] = round(sum(happy_scores) / len(happy_scores), 1) if happy_scores else 50

        option_rankings = sorted(per_option, key=per_option.get, reverse=True)
        best = option_rankings[0] if option_rankings else "Unknown"
        score = round(per_option.get(best, 50), 1)

        income_happiness_tradeoff = min(max(0, (per_option.get("Stay in Corporate", 50) - per_option.get("Start Company", 50))), 20)
        purpose_boost = min(profile.risk_tolerance * 10, 10)

        impact_factors = [
            {"factor": "Purpose Alignment", "value": best, "delta": round(purpose_boost, 1)},
            {"factor": "Income-Happiness Tradeoff", "value": f"{'Corporate > Startup' if income_happiness_tradeoff > 5 else 'Startup > Corporate'}", "delta": round(-income_happiness_tradeoff if income_happiness_tradeoff > 5 else income_happiness_tradeoff, 1)},
            {"factor": "Regret Minimization", "value": f"{per_option.get(best, 50):.0f}/100", "delta": round(per_option.get(best, 50) * 0.2, 1)},
        ]

        evidence = [
            f"Happiest path: {best} ({score:.0f}/100)",
            f"Purpose alignment score: +{purpose_boost:.0f}pts",
            f"Happiness derived from: purpose 30%, fulfillment 40%, low regret 20%, growth 10%",
        ]

        return AgentOutput(
            agent_name=self.name, score=round(score, 1), confidence=72,
            reasoning=f"Happiness analysis for {decision}. Highest life satisfaction path: {best}. "
                      f"Happiness is driven more by purpose and low regret than by income. "
                      f"{'Income-focused paths may trade off life satisfaction.' if income_happiness_tradeoff > 10 else 'Income and happiness are well-balanced here.'}",
            evidence=evidence,
            assumptions=["Happiness is multi-dimensional", "Purpose drives long-term satisfaction", "Regret minimization increases happiness"],
            risks=["Chasing income alone leads to dissatisfaction", "Ignoring purpose causes mid-life crisis", "Happiness adaptation - gains are temporary"],
            opportunities=[f"{best} aligns purpose with action", "Compound happiness from meaningful work"],
            recommendation=f"Happiest path: {best}",
            impact="positive" if score > 55 else "neutral",
            per_option_scores=per_option, option_rankings=option_rankings,
            tension_with=["financial", "career"],
            score_changes={"income_happiness_tradeoff": round(income_happiness_tradeoff, 1), "purpose_boost": round(purpose_boost, 1)},
            data_used=["happiness_score", "purpose_score", "regret_score", "learning_growth"],
            impact_factors=impact_factors,
            verdict=f"{best} will make you happiest long-term",
        )
