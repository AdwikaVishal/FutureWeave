"""Universal Financial Agent."""
from agents.universal.base import BaseAgent, AgentOutput


class FinancialAgent(BaseAgent):
    name = "financial"

    def evaluate(self, timelines, decision_type, anchors):
        tl_b = timelines.get("B", {})
        income_key = "income" if "income" in tl_b.get("Year1", {}) else "admission_probability"
        fin_scores = [tl_b.get(y, {}).get(income_key, 50) for y in ["Year1", "Year3", "Year5", "Year10"]]
        avg = sum(fin_scores) / len(fin_scores)

        reasoning_map = {
            "educational": f"Financial outlook at {avg:.0f}/100 — earning potential based on field selection.",
            "career": f"Wealth accumulation at {avg:.0f}/100 — salary trajectory and savings rate.",
            "financial": f"Portfolio performance at {avg:.0f}/100 — returns net of inflation and taxes.",
            "relocation": f"Financial impact at {avg:.0f}/100 — cost of living vs salary differential.",
            "business": f"Financial viability at {avg:.0f}/100 — revenue potential and funding access.",
            "health": f"Financial burden at {avg:.0f}/100 — treatment costs and income impact.",
        }

        return AgentOutput(
            score=round(avg, 1),
            reasoning=reasoning_map.get(decision_type, reasoning_map["career"]),
            evidence=["Income/earning potential tracked across 10 years", "Multiple scenarios factored"],
            confidence=round(0.65 + avg / 100.0 * 0.25, 2),
        )
