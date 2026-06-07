from contexts.base import ContextBuilder, SCORE_CLAMP


class LifestyleContextBuilder(ContextBuilder):
    def ignore_income(self) -> bool:
        return False

    def primary_metrics(self) -> list[str]:
        return ["fulfillment", "happiness", "work_life_balance", "personal_growth"]

    def build_anchors(self, data: dict) -> dict:
        return {
            "financial_cushion": data.get("financial_cushion", 55),
            "skill_portability": data.get("skill_portability", 60),
            "social_support": data.get("social_support", 65),
            "location_freedom": data.get("location_freedom", 50),
            "income_stability": data.get("income_stability", 55),
            "lifestyle_fit": data.get("lifestyle_fit", 60),
            "psychographic_bases": {"stress": 50, "health": 62, "happiness": 55},
        }

    def build_initial_scores(self, data: dict) -> dict[str, dict[str, float]]:
        fi = data.get("financial_cushion", 55)
        sp = data.get("skill_portability", 60)
        ss = data.get("social_support", 65)
        lf = data.get("lifestyle_fit", 60)
        return {
            "A": {
                "fulfillment": SCORE_CLAMP(55),
                "work_life_balance": SCORE_CLAMP(68),
                "personal_growth": SCORE_CLAMP(50),
                "social_connection": SCORE_CLAMP(ss + 5),
                "financial_freedom": SCORE_CLAMP(fi + 5),
                "stress": 42,
                "happiness": 58,
                "health": 65,
            },
            "B": {
                "fulfillment": SCORE_CLAMP(62),
                "work_life_balance": SCORE_CLAMP(55),
                "personal_growth": SCORE_CLAMP(62),
                "social_connection": SCORE_CLAMP(ss),
                "financial_freedom": SCORE_CLAMP(fi),
                "stress": 52,
                "happiness": 60,
                "health": 60,
            },
            "C": {
                "fulfillment": SCORE_CLAMP(72),
                "work_life_balance": SCORE_CLAMP(38),
                "personal_growth": SCORE_CLAMP(72),
                "social_connection": SCORE_CLAMP(ss - 10),
                "financial_freedom": SCORE_CLAMP(fi - 10),
                "stress": 65,
                "happiness": 55,
                "health": 52,
            },
        }
