"""Future Self Agent — long-term reflection."""
from agents.universal.base import BaseAgent, AgentOutput


class FutureSelfAgent(BaseAgent):
    name = "future_self"

    def evaluate(self, timelines, decision_type, anchors):
        tl_b = timelines.get("B", {})
        yr10 = tl_b.get("Year10", {})
        yr1 = tl_b.get("Year1", {})

        dimensions = []
        for key in yr10:
            if key in yr1 and isinstance(yr10[key], (int, float)) and isinstance(yr1[key], (int, float)):
                dimensions.append(yr10[key] - yr1[key])

        growth = sum(dimensions) / len(dimensions) if dimensions else 0
        future_score = min(100, max(0, 50 + growth))

        reasoning_map = {
            "educational": f"Future self projection at {future_score:.0f}/100 — degree pathway shapes long-term trajectory.",
            "career": f"Future self at {future_score:.0f}/100 — career arc shows meaningful progression.",
            "financial": f"Future wealth at {future_score:.0f}/100 — compounding returns build long-term security.",
            "relocation": f"Future self at {future_score:.0f}/100 — relocation opens new life possibilities.",
            "business": f"Future venture at {future_score:.0f}/100 — business scale and impact potential.",
            "health": f"Future health at {future_score:.0f}/100 — treatment outcome improves long-term wellbeing.",
        }

        return AgentOutput(
            score=round(future_score, 1),
            reasoning=reasoning_map.get(decision_type, reasoning_map["career"]),
            evidence=["10-year trajectory analyzed across all dimensions", "Growth delta from Year1 to Year10 computed"],
            confidence=round(0.50 + future_score / 100.0 * 0.35, 2),
        )
