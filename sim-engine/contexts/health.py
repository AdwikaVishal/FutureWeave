from contexts.base import ContextBuilder, SCORE_CLAMP


class HealthContextBuilder(ContextBuilder):
    def ignore_income(self) -> bool:
        return True

    def primary_metrics(self) -> list[str]:
        return ["treatment_success", "recovery_time", "quality_of_life", "risk_level"]

    def build_anchors(self, data: dict) -> dict:
        return {
            "treatment_success_rate": data.get("treatment_success_rate", 70),
            "recovery_time_months": data.get("recovery_time_months", 6),
            "treatment_cost_score": data.get("treatment_cost_score", 50),
            "quality_of_life_impact": data.get("quality_of_life_impact", 25),
            "side_effect_risk": data.get("side_effect_risk", 30),
            "alternative_effectiveness": data.get("alternative_effectiveness", 55),
            "live_cpi": data.get("live_cpi"),
            "psychographic_bases": {"stress": 55, "health": 60, "relationships": 58, "happiness": 55},
        }

    def build_initial_scores(self, data: dict) -> dict[str, dict[str, float]]:
        ts = data.get("treatment_success_rate", 70)
        qol = 100 - data.get("quality_of_life_impact", 25)
        risk = 100 - data.get("side_effect_risk", 30)
        return {
            "A": {
                "treatment_success": SCORE_CLAMP(ts - 5),
                "quality_of_life": SCORE_CLAMP(qol + 5),
                "recovery_progress": SCORE_CLAMP(60),
                "risk_level": SCORE_CLAMP(risk + 5),
                "stress": 55,
                "health": 55,
                "relationships": 60,
                "happiness": 50,
                "opportunity": SCORE_CLAMP(50),
            },
            "B": {
                "treatment_success": SCORE_CLAMP(ts + 5),
                "quality_of_life": SCORE_CLAMP(qol),
                "recovery_progress": SCORE_CLAMP(70),
                "risk_level": SCORE_CLAMP(risk),
                "stress": 58,
                "health": 60,
                "relationships": 58,
                "happiness": 55,
                "opportunity": SCORE_CLAMP(55),
            },
            "C": {
                "treatment_success": SCORE_CLAMP(ts + 15),
                "quality_of_life": SCORE_CLAMP(qol - 10),
                "recovery_progress": SCORE_CLAMP(80),
                "risk_level": SCORE_CLAMP(risk - 10),
                "stress": 65,
                "health": 65,
                "relationships": 50,
                "happiness": 52,
                "opportunity": SCORE_CLAMP(60),
            },
        }
