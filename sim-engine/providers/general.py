from providers.base import DecisionProvider, ProviderContext, ProviderResult


class GeneralProvider(DecisionProvider):
    """Fallback provider for unclassified decisions."""

    def collect(self, ctx: ProviderContext) -> ProviderResult:
        return ProviderResult(
            context_data={
                "default_score": 50,
            },
            warnings=["General decision type — limited context-specific data available."],
            confidence=60,
        )

    def metric_labels(self) -> list[str]:
        return ["General Score"]

    def timeline_years(self) -> list[str]:
        return ["Year1", "Year3", "Year5", "Year10"]

    def timeline_templates(self) -> dict:
        return {
            "Year1": "Start",
            "Year3": "Progress Check",
            "Year5": "Mid-Point",
            "Year10": "Outcome",
        }
