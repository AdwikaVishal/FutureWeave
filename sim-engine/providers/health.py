from providers.base import DecisionProvider, ProviderContext, ProviderResult


class HealthProvider(DecisionProvider):
    """Provider for health decisions (treatment plans, procedures, etc.).
    Uses medical outcomes, cost, recovery data.
    """

    def collect(self, ctx: ProviderContext) -> ProviderResult:
        data = {
            "treatment_success_rate": 75,
            "recovery_time_months": 6,
            "treatment_cost_score": 55,
            "quality_of_life_impact": 20,
            "side_effect_risk": 30,
            "alternative_effectiveness": 60,
            "live_cpi": 5.0,
        }
        return ProviderResult(
            context_data=data,
            warnings=[],
            confidence=80,
        )

    def metric_labels(self) -> list[str]:
        return [
            "Treatment Success",
            "Recovery Time",
            "Cost Burden",
            "Quality of Life",
            "Risk Level",
        ]

    def timeline_years(self) -> list[str]:
        return ["Year1", "Year3", "Year5", "Year10"]

    def timeline_templates(self) -> dict:
        return {
            "Year1": "Treatment & Recovery",
            "Year3": "Rehabilitation & Adaptation",
            "Year5": "Stability & Maintenance",
            "Year10": "Long-Term Outcome",
        }
