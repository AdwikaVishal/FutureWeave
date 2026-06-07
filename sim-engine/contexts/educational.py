from contexts.base import ContextBuilder, SCORE_CLAMP


class EducationalContextBuilder(ContextBuilder):
    def ignore_income(self) -> bool:
        return True

    def primary_metrics(self) -> list[str]:
        return ["admission_probability", "placement_outlook", "higher_studies_options", "learning_curve"]

    def build_anchors(self, data: dict) -> dict:
        return {
            "admission_probability": data.get("admission_probability", 65),
            "college_quality": data.get("college_quality", 70),
            "seat_availability": data.get("seat_availability", 60),
            "placement_outlook": data.get("placement_outlook", 72),
            "higher_studies_options": data.get("higher_studies_options", 68),
            "learning_curve": data.get("learning_curve", 75),
            "field_demand_growth": data.get("field_demand_growth", 8.0),
            "exam_difficulty": data.get("exam_difficulty", 60),
            "psychographic_bases": {"stress": 55, "health": 65, "relationships": 60, "happiness": 52},
        }

    def build_initial_scores(self, data: dict) -> dict[str, dict[str, float]]:
        ap = data.get("admission_probability", 65)
        co = data.get("college_quality", 70)
        po = data.get("placement_outlook", 72)
        hs = data.get("higher_studies_options", 68)
        lc = data.get("learning_curve", 75)
        return {
            "A": {
                "admission_probability": SCORE_CLAMP(ap - 5),
                "college_quality": SCORE_CLAMP(co - 3),
                "placement_outlook": SCORE_CLAMP(po - 8),
                "higher_studies_options": SCORE_CLAMP(hs + 5),
                "learning_curve": SCORE_CLAMP(lc - 5),
                "stress": 45,
                "health": 70,
                "relationships": 68,
                "happiness": 60,
                "opportunity": SCORE_CLAMP(po - 5),
            },
            "B": {
                "admission_probability": SCORE_CLAMP(ap + 5),
                "college_quality": SCORE_CLAMP(co + 5),
                "placement_outlook": SCORE_CLAMP(po + 5),
                "higher_studies_options": SCORE_CLAMP(hs),
                "learning_curve": SCORE_CLAMP(lc + 3),
                "stress": 52,
                "health": 62,
                "relationships": 55,
                "happiness": 56,
                "opportunity": SCORE_CLAMP(po + 10),
            },
            "C": {
                "admission_probability": SCORE_CLAMP(ap + 10),
                "college_quality": SCORE_CLAMP(co + 8),
                "placement_outlook": SCORE_CLAMP(po + 12),
                "higher_studies_options": SCORE_CLAMP(hs - 8),
                "learning_curve": SCORE_CLAMP(lc + 10),
                "stress": 62,
                "health": 55,
                "relationships": 48,
                "happiness": 50,
                "opportunity": SCORE_CLAMP(po + 18),
            },
        }
