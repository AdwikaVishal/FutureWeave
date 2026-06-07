from contexts.base import ContextBuilder, SCORE_CLAMP


class RelocationContextBuilder(ContextBuilder):
    def ignore_income(self) -> bool:
        return False

    def primary_metrics(self) -> list[str]:
        return ["visa_success", "quality_of_life", "safety", "employment_success"]

    def build_anchors(self, data: dict) -> dict:
        return {
            "visa_probability": data.get("visa_probability", 60),
            "cost_of_living_index": data.get("cost_of_living_index", 100),
            "safety_score": data.get("safety_score", 70),
            "healthcare_quality": data.get("healthcare_quality", 70),
            "quality_of_life": data.get("quality_of_life", 70),
            "integration_difficulty": data.get("integration_difficulty", 50),
            "employment_success_probability": data.get("employment_success_probability", 65),
            "cultural_fit": data.get("cultural_fit", 60),
            "live_unemployment": data.get("live_unemployment"),
            "live_gdp_growth": data.get("live_gdp_growth"),
            "psychographic_bases": {"stress": 60, "health": 65, "relationships": 55, "happiness": 60},
        }

    def build_initial_scores(self, data: dict) -> dict[str, dict[str, float]]:
        vp = data.get("visa_probability", 60)
        qol = data.get("quality_of_life", 70)
        saf = data.get("safety_score", 70)
        emp = data.get("employment_success_probability", 65)
        return {
            "A": {
                "visa_success": SCORE_CLAMP(vp - 5),
                "quality_of_life": SCORE_CLAMP(qol + 5),
                "safety": SCORE_CLAMP(saf + 5),
                "employment_success": SCORE_CLAMP(emp - 10),
                "stress": 55,
                "health": 68,
                "relationships": 50,
                "happiness": 55,
                "opportunity": SCORE_CLAMP(60),
            },
            "B": {
                "visa_success": SCORE_CLAMP(vp + 5),
                "quality_of_life": SCORE_CLAMP(qol),
                "safety": SCORE_CLAMP(saf),
                "employment_success": SCORE_CLAMP(emp + 5),
                "stress": 60,
                "health": 62,
                "relationships": 55,
                "happiness": 65,
                "opportunity": SCORE_CLAMP(72),
            },
            "C": {
                "visa_success": SCORE_CLAMP(vp + 12),
                "quality_of_life": SCORE_CLAMP(qol - 5),
                "safety": SCORE_CLAMP(saf - 5),
                "employment_success": SCORE_CLAMP(emp + 15),
                "stress": 70,
                "health": 55,
                "relationships": 45,
                "happiness": 58,
                "opportunity": SCORE_CLAMP(80),
            },
        }
