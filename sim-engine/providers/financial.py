from providers.base import DecisionProvider, ProviderContext, ProviderResult


class FinancialProvider(DecisionProvider):
    """Provider for financial decisions (invest, buy vs rent, etc.).
    Uses interest rates, market returns, macro indicators.
    """

    def collect(self, ctx: ProviderContext) -> ProviderResult:
        data = {
            "interest_rate": 6.5,
            "market_return_expected": 10.0,
            "inflation_rate": 5.0,
            "tax_rate": 30.0,
            "risk_free_rate": 3.0,
            "real_estate_appreciation": 7.0,
            "live_cpi": 5.0,
            "live_gdp_growth": 6.5,
        }
        return ProviderResult(
            context_data=data,
            warnings=[],
            confidence=85,
        )

    def metric_labels(self) -> list[str]:
        return [
            "Interest Rate",
            "Market Return",
            "Inflation",
            "Tax Efficiency",
            "Risk Premium",
        ]

    def timeline_years(self) -> list[str]:
        return ["Year1", "Year3", "Year5", "Year10"]

    def timeline_templates(self) -> dict:
        return {
            "Year1": "Initial Investment",
            "Year3": "Growth Phase",
            "Year5": "Compounding Acceleration",
            "Year10": "Wealth Milestone",
        }
