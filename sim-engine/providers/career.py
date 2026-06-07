from providers.base import DecisionProvider, ProviderContext, ProviderResult


class CareerProvider(DecisionProvider):
    """Provider for career decisions (job switch, promotion, etc.).
    Uses salary, demand, growth, macro indicators.
    """

    def collect(self, ctx: ProviderContext) -> ProviderResult:
        data = {
            "salary_entry_lpa": 6.0,
            "salary_mid_lpa": 15.0,
            "salary_senior_lpa": 28.0,
            "demand_score": 72,
            "automation_risk": 25,
            "skill_gap": 45,
            "growth_rate": 8.2,
            "live_unemployment": 4.2,
            "live_cpi": 5.0,
            "live_gdp_growth": 6.5,
            "employment_rate": 0.96,
        }
        return ProviderResult(
            context_data=data,
            warnings=[],
            confidence=85,
        )

    def metric_labels(self) -> list[str]:
        return [
            "Salary",
            "Demand",
            "Automation Risk",
            "Skill Gap",
            "Growth Rate",
        ]

    def timeline_years(self) -> list[str]:
        return ["Year1", "Year3", "Year5", "Year10"]

    def timeline_templates(self) -> dict:
        return {
            "Year1": "Career Start",
            "Year3": "Growth & Promotion",
            "Year5": "Mid-Career Inflection",
            "Year10": "Senior Leadership",
        }
