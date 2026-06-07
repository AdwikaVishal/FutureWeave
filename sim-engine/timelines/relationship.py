from timelines.base import TimelineGenerator, _causal_transition, _clamp


class RelationshipTimelineGenerator(TimelineGenerator):
    def node_names(self) -> list[str]:
        return [
            "emotional_health", "compatibility", "communication",
            "personal_growth", "future_alignment", "stress",
            "happiness", "health",
        ]

    def generate(self, initial_scores: dict, anchors: dict, years: list[str]) -> dict:
        result = {}
        archetypes = {"A": initial_scores.get("A", {}), "B": initial_scores.get("B", {}), "C": initial_scores.get("C", {})}
        year_gaps = {"Year1": 1, "Year3": 2, "Year5": 2, "Year10": 5}

        for arch_key, year1 in archetypes.items():
            prev = dict(year1)
            arch_data = {}
            for yr in years:
                if yr == "Year1":
                    arch_data[yr] = dict(prev)
                else:
                    prev = _causal_transition(prev, year_gaps.get(yr, 1))
                    arch_data[yr] = dict(prev)
            result[arch_key] = arch_data

        return result
