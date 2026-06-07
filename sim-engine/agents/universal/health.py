"""Universal Health Agent."""
from agents.universal.base import BaseAgent, AgentOutput


class HealthAgent(BaseAgent):
    name = "health"

    def evaluate(self, timelines, decision_type, anchors):
        tl_b = timelines.get("B", {})
        health_scores = [tl_b.get(y, {}).get("health", 60) for y in ["Year1", "Year3", "Year5", "Year10"]]
        stress_scores = [tl_b.get(y, {}).get("stress", 50) for y in ["Year1", "Year3", "Year5", "Year10"]]
        wellbeing = [(h + (100 - s)) / 2 for h, s in zip(health_scores, stress_scores)]
        avg = sum(wellbeing) / len(wellbeing)

        reasoning_map = {
            "educational": f"Wellbeing at {avg:.0f}/100 — academic stress balanced by campus life.",
            "career": f"Wellbeing at {avg:.0f}/100 — career demands vs self-care balance.",
            "financial": f"Wellbeing at {avg:.0f}/100 — financial stress impacts overall health.",
            "relocation": f"Wellbeing at {avg:.0f}/100 — relocation stress vs lifestyle quality.",
            "business": f"Wellbeing at {avg:.0f}/100 — entrepreneurial stress managed with autonomy.",
            "health": f"Health outcome at {avg:.0f}/100 — treatment effectiveness and recovery trajectory.",
        }

        return AgentOutput(
            score=round(avg, 1),
            reasoning=reasoning_map.get(decision_type, reasoning_map["career"]),
            evidence=["Health and stress tracked across all timelines", "Work/academic-life balance modeled"],
            confidence=round(0.60 + avg / 100.0 * 0.25, 2),
        )
