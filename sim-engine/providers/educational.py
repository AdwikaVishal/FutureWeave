from providers.base import DecisionProvider, ProviderContext, ProviderResult


class EducationalProvider(DecisionProvider):
    """Provider for educational decisions (NEET vs JEE, CSE vs AIML, etc.).
    No GDP, no inflation, no salary data.
    """

    def collect(self, ctx: ProviderContext) -> ProviderResult:
        data = {
            "admission_probability": 65,
            "college_quality": 70,
            "seat_availability": 60,
            "placement_outlook": 72,
            "higher_studies_options": 68,
            "learning_curve": 75,
            "field_demand_growth": 8.5,
            "exam_difficulty": 60,
        }
        return ProviderResult(
            context_data=data,
            warnings=[],
            confidence=80,
        )

    def metric_labels(self) -> list[str]:
        return [
            "Admission Probability",
            "College Quality",
            "Seat Availability",
            "Placement Outlook",
            "Higher Studies Options",
            "Learning Curve",
        ]

    def timeline_years(self) -> list[str]:
        return ["Year1", "Year3", "Year5", "Year10"]

    def timeline_templates(self) -> dict:
        return {
            "Year1": "Preparation & Entrance",
            "Year3": "College Admission & Foundation",
            "Year5": "Degree Completion & Placements",
            "Year10": "Career Outcome Post-Graduation",
        }
