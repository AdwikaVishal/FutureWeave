"""Universal Relationship Agent."""
from agents.universal.base import BaseAgent, AgentOutput


class RelationshipAgent(BaseAgent):
    name = "relationship"

    def evaluate(self, timelines, decision_type, anchors):
        tl_b = timelines.get("B", {})
        rel_scores = [tl_b.get(y, {}).get("relationships", 55) for y in ["Year1", "Year3", "Year5", "Year10"]]
        avg = sum(rel_scores) / len(rel_scores)

        reasoning_map = {
            "educational": f"Relationship index at {avg:.0f}/100 — campus networks and family bonds.",
            "career": f"Relationship index at {avg:.0f}/100 — social capital builds with intentional investment.",
            "financial": f"Relationship dynamics at {avg:.0f}/100 — financial decisions impact family/partners.",
            "relocation": f"Relationship index at {avg:.0f}/100 — building new social circles in new location.",
            "business": f"Relationship index at {avg:.0f}/100 — professional network and co-founder dynamics.",
            "health": f"Relationship support at {avg:.0f}/100 — caregiver and family support system.",
        }

        return AgentOutput(
            score=round(avg, 1),
            reasoning=reasoning_map.get(decision_type, reasoning_map["career"]),
            evidence=["Relationship scores tracked across time", "Social capital modeled as cumulative asset"],
            confidence=round(0.55 + avg / 100.0 * 0.3, 2),
        )
