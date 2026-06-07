from contexts.base import ContextBuilder, SCORE_CLAMP


class CareerContextBuilder(ContextBuilder):
    def ignore_income(self) -> bool:
        return False

    def primary_metrics(self) -> list[str]:
        return ["salary", "demand", "growth_rate", "skill_gap"]

    def build_anchors(self, data: dict) -> dict:
        entry = data.get("salary_entry_lpa")
        mid = data.get("salary_mid_lpa")
        senior = data.get("salary_senior_lpa")
        return {
            "salary_entry_lpa": entry,
            "salary_mid_lpa": mid,
            "salary_senior_lpa": senior,
            "demand_score": data.get("demand_score", 70),
            "automation_risk": data.get("automation_risk", 30),
            "skill_gap": data.get("skill_gap", 50),
            "growth_rate": data.get("growth_rate", 8.0),
            "live_unemployment": data.get("live_unemployment"),
            "live_cpi": data.get("live_cpi"),
            "live_gdp_growth": data.get("live_gdp_growth"),
            "employment_rate": data.get("employment_rate"),
            "psychographic_bases": {"stress": 55, "health": 65, "relationships": 60, "happiness": 52},
        }

    def build_initial_scores(self, data: dict) -> dict[str, dict[str, float]]:
        income_base = 30
        return {
            "A": {
                "income": SCORE_CLAMP(income_base - 3),
                "career_growth": 38,
                "stress": 45,
                "health": 72,
                "relationships": 72,
                "happiness": 62,
                "opportunity": SCORE_CLAMP(50 - 10),
            },
            "B": {
                "income": SCORE_CLAMP(income_base + 2),
                "career_growth": 52,
                "stress": 55,
                "health": 64,
                "relationships": 58,
                "happiness": 54,
                "opportunity": SCORE_CLAMP(50 + 3),
            },
            "C": {
                "income": SCORE_CLAMP(income_base + 6),
                "career_growth": 58,
                "stress": 65,
                "health": 58,
                "relationships": 48,
                "happiness": 50,
                "opportunity": SCORE_CLAMP(50 + 14),
            },
        }
