from providers.base import DecisionProvider, ProviderContext, ProviderResult


class LifestyleProvider(DecisionProvider):
    """Provider for lifestyle decisions (gap year, freelance, creative pursuit, location independence)."""

    def collect(self, ctx: ProviderContext) -> ProviderResult:
        data = {
            "financial_cushion": 55,
            "skill_portability": 60,
            "social_support": 65,
            "location_freedom": 50,
            "income_stability": 55,
            "lifestyle_fit": 60,
        }
        return ProviderResult(
            context_data=data,
            warnings=[],
            confidence=80,
        )

    def metric_labels(self) -> list[str]:
        return [
            "Fulfillment",
            "Work-Life Balance",
            "Personal Growth",
            "Social Connection",
            "Financial Freedom",
        ]

    def timeline_years(self) -> list[str]:
        return ["Year1", "Year3", "Year5", "Year10"]

    def timeline_templates(self) -> dict:
        return {
            "Year1": "New Path",
            "Year3": "Finding Rhythm",
            "Year5": "Deepening Practice",
            "Year10": "Integrated Life",
        }
