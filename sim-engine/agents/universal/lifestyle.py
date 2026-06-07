"""Universal Lifestyle Agent."""
from agents.universal.base import BaseAgent, AgentOutput


class LifestyleAgent(BaseAgent):
    name = "lifestyle"

    def evaluate(self, timelines, decision_type, anchors):
        tl_b = timelines.get("B", {})
        happiness = [tl_b.get(y, {}).get("happiness", 55) for y in ["Year1", "Year3", "Year5", "Year10"]]
        health = [tl_b.get(y, {}).get("health", 60) for y in ["Year1", "Year3", "Year5", "Year10"]]
        lifestyle = [(h + he) / 2 for h, he in zip(happiness, health)]
        avg = sum(lifestyle) / len(lifestyle)

        reasoning_map = {
            "educational": f"Lifestyle quality at {avg:.0f}/100 — academic life balance and campus experience.",
            "career": f"Lifestyle quality at {avg:.0f}/100 — work-life balance and personal fulfillment.",
            "financial": f"Lifestyle impact at {avg:.0f}/100 — financial choices enable lifestyle preferences.",
            "relocation": f"Lifestyle quality at {avg:.0f}/100 — new environment and cultural experiences.",
            "business": f"Lifestyle at {avg:.0f}/100 — entrepreneurial autonomy vs uncertainty trade-off.",
            "health": f"Lifestyle adjustment at {avg:.0f}/100 — adapting to health-related changes.",
        }

        return AgentOutput(
            score=round(avg, 1),
            reasoning=reasoning_map.get(decision_type, reasoning_map["career"]),
            evidence=["Happiness and health scores combined for lifestyle assessment", "Long-term satisfaction modeled"],
            confidence=round(0.55 + avg / 100.0 * 0.3, 2),
        )
