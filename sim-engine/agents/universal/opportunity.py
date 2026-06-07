"""Universal Opportunity Agent — works across all decision types."""
from agents.universal.base import BaseAgent, AgentOutput


class OpportunityAgent(BaseAgent):
    name = "opportunity"

    def evaluate(self, timelines, decision_type, anchors):
        tl_b = timelines.get("B", {})
        yr_scores = [tl_b.get(y, {}).get("opportunity", 50) for y in ["Year1", "Year3", "Year5", "Year10"]]
        avg = sum(yr_scores) / len(yr_scores)

        reasoning_map = {
            "educational": f"Opportunity landscape at {avg:.0f}/100 — field choice unlocks career pathways post-graduation.",
            "career": f"Opportunity landscape at {avg:.0f}/100 — career capital unlocks premium options by Year7.",
            "financial": f"Investment opportunity at {avg:.0f}/100 — market conditions favor growth.",
            "relocation": f"Relocation opportunity at {avg:.0f}/100 — destination offers quality-of-life upside.",
            "business": f"Business opportunity at {avg:.0f}/100 — market timing and size favorable.",
            "health": f"Health outcome opportunity at {avg:.0f}/100 — treatment pathway shows promise.",
        }

        evidence_map = {
            "educational": ["Placement records vary by specialization", "Higher studies expand long-term options"],
            "career": ["Industry growing at 8-12% annually", "Experience premium: senior roles command 2-3x entry salary"],
            "financial": ["Compounding returns over 10-year horizon", "Diversification reduces downside risk"],
            "relocation": ["Visa pathways exist for skilled professionals", "Growing expat communities ease integration"],
            "business": ["Market in growth phase", "First-mover advantage in emerging segments"],
            "health": ["Medical advancements improve outcomes", "Multiple treatment options available"],
        }

        return AgentOutput(
            score=round(avg, 1),
            reasoning=reasoning_map.get(decision_type, reasoning_map["career"]),
            evidence=evidence_map.get(decision_type, evidence_map["career"]),
            confidence=round(0.65 + avg / 100.0 * 0.25, 2),
        )
