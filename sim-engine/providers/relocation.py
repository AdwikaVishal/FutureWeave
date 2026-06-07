from providers.base import DecisionProvider, ProviderContext, ProviderResult


class RelocationProvider(DecisionProvider):
    """Provider for relocation decisions (move abroad, change city, etc.).
    Uses visa, cost of living, safety, quality of life indicators.
    """

    def collect(self, ctx: ProviderContext) -> ProviderResult:
        data = {
            "visa_probability": 65,
            "cost_of_living_index": 120,
            "safety_score": 75,
            "healthcare_quality": 72,
            "quality_of_life": 70,
            "integration_difficulty": 45,
            "employment_success_probability": 68,
            "cultural_fit": 60,
            "live_unemployment": 4.2,
            "live_gdp_growth": 6.5,
        }
        return ProviderResult(
            context_data=data,
            warnings=[],
            confidence=80,
        )

    def metric_labels(self) -> list[str]:
        return [
            "Visa Success",
            "Cost of Living",
            "Safety",
            "Healthcare",
            "Quality of Life",
        ]

    def timeline_years(self) -> list[str]:
        return ["Year1", "Year3", "Year5", "Year10"]

    def timeline_templates(self) -> dict:
        return {
            "Year1": "Migration & Settlement",
            "Year3": "Integration & Employment",
            "Year5": "Permanent Residency Pathway",
            "Year10": "Long-Term Stability",
        }
