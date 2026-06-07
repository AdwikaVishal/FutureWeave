from providers.base import DecisionProvider, ProviderContext, ProviderResult


class BusinessProvider(DecisionProvider):
    """Provider for business/startup decisions.
    Uses market size, competition, funding, macro indicators.
    """

    def collect(self, ctx: ProviderContext) -> ProviderResult:
        data = {
            "market_size_score": 70,
            "competition_intensity": 55,
            "funding_availability": 60,
            "failure_rate_5yr": 50,
            "profitability_timeline_years": 3,
            "regulatory_difficulty": 35,
            "live_gdp_growth": 6.5,
            "live_cpi": 5.0,
        }
        return ProviderResult(
            context_data=data,
            warnings=[],
            confidence=80,
        )

    def metric_labels(self) -> list[str]:
        return [
            "Market Size",
            "Competition",
            "Funding Access",
            "Success Rate",
            "Regulatory Ease",
        ]

    def timeline_years(self) -> list[str]:
        return ["Year1", "Year3", "Year5", "Year10"]

    def timeline_templates(self) -> dict:
        return {
            "Year1": "Launch & Validation",
            "Year3": "Growth & Traction",
            "Year5": "Scale or Pivot",
            "Year10": "Maturity & Exit",
        }
