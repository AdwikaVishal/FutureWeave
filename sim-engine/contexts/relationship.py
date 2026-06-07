from contexts.base import ContextBuilder, SCORE_CLAMP


class RelationshipContextBuilder(ContextBuilder):
    def ignore_income(self) -> bool:
        return True

    def primary_metrics(self) -> list[str]:
        return ["emotional_health", "compatibility", "communication", "future_alignment"]

    def build_anchors(self, data: dict) -> dict:
        return {
            "compatibility_score": data.get("compatibility_score", 65),
            "communication_quality": data.get("communication_quality", 60),
            "shared_values": data.get("shared_values", 70),
            "conflict_resolution": data.get("conflict_resolution", 55),
            "external_pressure": data.get("external_pressure", 40),
            "long_term_potential": data.get("long_term_potential", 68),
            "life_stage_alignment": data.get("life_stage_alignment", 62),
            "psychographic_bases": {"stress": 50, "health": 65, "happiness": 55},
        }

    def build_initial_scores(self, data: dict) -> dict[str, dict[str, float]]:
        cm = data.get("compatibility_score", 65)
        cq = data.get("communication_quality", 60)
        sv = data.get("shared_values", 70)
        lt = data.get("long_term_potential", 68)
        return {
            "A": {
                "emotional_health": SCORE_CLAMP(65),
                "compatibility": SCORE_CLAMP(cm + 5),
                "communication": SCORE_CLAMP(cq + 3),
                "personal_growth": SCORE_CLAMP(48),
                "future_alignment": SCORE_CLAMP(sv + 5),
                "stress": 42,
                "happiness": 62,
                "health": 68,
            },
            "B": {
                "emotional_health": SCORE_CLAMP(58),
                "compatibility": SCORE_CLAMP(cm),
                "communication": SCORE_CLAMP(cq + 5),
                "personal_growth": SCORE_CLAMP(58),
                "future_alignment": SCORE_CLAMP(lt),
                "stress": 52,
                "happiness": 56,
                "health": 62,
            },
            "C": {
                "emotional_health": SCORE_CLAMP(48),
                "compatibility": SCORE_CLAMP(cm - 8),
                "communication": SCORE_CLAMP(cq + 8),
                "personal_growth": SCORE_CLAMP(68),
                "future_alignment": SCORE_CLAMP(lt - 10),
                "stress": 62,
                "happiness": 52,
                "health": 58,
            },
        }
