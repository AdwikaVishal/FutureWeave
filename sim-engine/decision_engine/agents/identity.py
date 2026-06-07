from __future__ import annotations
import logging
from typing import Any, Dict, List
from . import BaseAgent
from ..types import AgentOutput, UserProfile, EconomicData, FuturePath, DecisionOption, SIMULATION_YEARS

logger = logging.getLogger(__name__)


class IdentityAgent(BaseAgent):
    name = "identity"

    def analyze(self, decision: str, profile: UserProfile, economic: EconomicData, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> AgentOutput:
        per_option = {}
        for opt in options:
            path = future_paths.get(opt.title)
            if not path:
                per_option[opt.title] = 50.0
                continue
            identity_scores = []
            for yk in SIMULATION_YEARS:
                ys = path.years.get(yk)
                if ys:
                    combined = ys.purpose * 0.35 + ys.learning_growth * 0.25 + ys.freedom * 0.2 + (100 - ys.regret) * 0.2
                    identity_scores.append(combined)
            per_option[opt.title] = round(sum(identity_scores) / len(identity_scores), 1) if identity_scores else 50

        option_rankings = sorted(per_option, key=per_option.get, reverse=True)
        best = option_rankings[0] if option_rankings else "Unknown"
        score = round(per_option.get(best, 50), 1)

        alignment_with_values = min(profile.risk_tolerance * 20 + (1 if "start" in decision.lower() or "found" in decision.lower() else 0) * 15, 30)
        score = min(100, score + alignment_with_values * 0.3)

        impact_factors = [
            {"factor": "Values Alignment", "value": best, "delta": round(alignment_with_values, 1)},
            {"factor": "Personal Growth", "value": f"{per_option.get(best, 50):.0f}/100", "delta": round(per_option.get(best, 50) * 0.15, 1)},
            {"factor": "Freedom Score", "value": "Across paths", "delta": round(min(profile.risk_tolerance * 20, 15), 1)},
        ]

        evidence = [
            f"Best identity alignment: {best} ({per_option.get(best, 50):.0f}/100)",
            f"Values alignment bonus: +{alignment_with_values:.0f}pts",
            f"Risk tolerance suggests {'entrepreneurial' if profile.risk_tolerance > 0.6 else 'balanced'} identity",
            f"Decision '{decision}' aligns with {'growth' if 'start' in decision.lower() or 'found' in decision.lower() else 'stable'} identity",
        ]

        return AgentOutput(
            agent_name=self.name, score=round(score, 1), confidence=70,
            reasoning=f"Identity analysis for {decision}. Path most aligned with your values: {best}. "
                      f"Your risk tolerance ({profile.risk_tolerance:.2f}) suggests you value "
                      f"{'autonomy and growth' if profile.risk_tolerance > 0.6 else 'security and balance'} in your identity. "
                      f"{'This decision strongly aligns with an entrepreneurial identity.' if 'start' in decision.lower() or 'found' in decision.lower() else 'This decision aligns with a growth-through-stability identity.'}",
            evidence=evidence,
            assumptions=["Identity evolves with decisions", "Values alignment predicts long-term satisfaction", "Authenticity matters more than income"],
            risks=["Identity crisis from misaligned decisions", "Social pressure may override personal values", "Identity inertia - hard to change paths"],
            opportunities=[f"{best} allows authentic self-expression", "Identity compounds through aligned decisions"],
            recommendation=f"Identity-aligned path: {best}",
            impact="positive" if score > 55 else "neutral",
            per_option_scores=per_option, option_rankings=option_rankings,
            tension_with=["financial", "risk"],
            score_changes={"values_alignment": round(alignment_with_values, 1)},
            data_used=["risk_tolerance", "purpose_score", "learning_growth", "freedom_score"],
            impact_factors=impact_factors,
            verdict=f"{best} aligns with who you are",
        )
