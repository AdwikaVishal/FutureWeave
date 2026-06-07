from providers.base import DecisionProvider, ProviderContext, ProviderResult


class RelationshipProvider(DecisionProvider):
    """Provider for relationship decisions (marriage, commitment, break-up, partnership)."""

    def collect(self, ctx: ProviderContext) -> ProviderResult:
        data = {
            "compatibility_score": 68,
            "communication_quality": 62,
            "shared_values": 70,
            "conflict_resolution": 55,
            "external_pressure": 40,
            "long_term_potential": 65,
            "life_stage_alignment": 60,
        }
        return ProviderResult(
            context_data=data,
            warnings=[],
            confidence=80,
        )

    def metric_labels(self) -> list[str]:
        return [
            "Emotional Health",
            "Compatibility",
            "Communication",
            "Personal Growth",
            "Future Alignment",
        ]

    def timeline_years(self) -> list[str]:
        return ["Year1", "Year3", "Year5", "Year10"]

    def timeline_templates(self) -> dict:
        return {
            "Year1": "Bonding & Foundation",
            "Year3": "Deepening & Challenges",
            "Year5": "Commitment & Growth",
            "Year10": "Shared Life & Partnership",
        }
