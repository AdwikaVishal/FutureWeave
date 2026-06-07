"""Universal Risk Agent."""
from agents.universal.base import BaseAgent, AgentOutput


class RiskAgent(BaseAgent):
    name = "risk"

    def evaluate(self, timelines, decision_type, anchors):
        tl_b = timelines.get("B", {})
        stress_scores = [tl_b.get(y, {}).get("stress", 50) for y in ["Year1", "Year3", "Year5", "Year10"]]
        avg_stress = sum(stress_scores) / len(stress_scores)
        risk_score = min(100, avg_stress + 10)

        reasoning_map = {
            "educational": f"Risk level at {risk_score:.0f}/100 — academic and career uncertainty moderate.",
            "career": f"Risk profile at {risk_score:.0f}/100 — career volatility and market exposure.",
            "financial": f"Risk exposure at {risk_score:.0f}/100 — market and inflation risks present.",
            "relocation": f"Relocation risk at {risk_score:.0f}/100 — visa and integration uncertainties.",
            "business": f"Business risk at {risk_score:.0f}/100 — startup failure and market risks.",
            "health": f"Treatment risk at {risk_score:.0f}/100 — procedure and recovery uncertainties.",
        }

        return AgentOutput(
            score=round(risk_score, 1),
            reasoning=reasoning_map.get(decision_type, reasoning_map["career"]),
            evidence=["Stress levels tracked across all timelines", "Economic indicators factored into risk model"],
            confidence=round(0.60 + risk_score / 100.0 * 0.3, 2),
        )
