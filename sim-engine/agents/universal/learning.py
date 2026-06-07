"""Universal Learning Agent."""
from agents.universal.base import BaseAgent, AgentOutput


class LearningAgent(BaseAgent):
    name = "learning"

    def evaluate(self, timelines, decision_type, anchors):
        tl_b = timelines.get("B", {})

        if decision_type == "educational":
            lc_scores = [tl_b.get(y, {}).get("learning_curve", 50) for y in ["Year1", "Year3", "Year5", "Year10"]]
        elif decision_type == "career":
            lc_scores = [tl_b.get(y, {}).get("career_growth", 50) for y in ["Year1", "Year3", "Year5", "Year10"]]
        elif decision_type == "business":
            lc_scores = [tl_b.get(y, {}).get("revenue_potential", 50) for y in ["Year1", "Year3", "Year5", "Year10"]]
        else:
            lc_scores = [50, 55, 60, 65]

        avg = sum(lc_scores) / len(lc_scores)

        reasoning_map = {
            "educational": f"Learning trajectory at {avg:.0f}/100 — curriculum and skill development pace.",
            "career": f"Skill growth at {avg:.0f}/100 — professional development and upskilling opportunities.",
            "financial": f"Financial literacy growth at {avg:.0f}/100 — investment knowledge compounds over time.",
            "relocation": f"Cultural learning at {avg:.0f}/100 — language and integration progress.",
            "business": f"Entrepreneurial learning at {avg:.0f}/100 — business acumen develops through experience.",
            "health": f"Health literacy at {avg:.0f}/100 — understanding of condition and treatment grows.",
        }

        return AgentOutput(
            score=round(avg, 1),
            reasoning=reasoning_map.get(decision_type, reasoning_map["educational"]),
            evidence=["Learning curves modeled across decision timeline", "Skill acquisition rates factored"],
            confidence=round(0.60 + avg / 100.0 * 0.3, 2),
        )
