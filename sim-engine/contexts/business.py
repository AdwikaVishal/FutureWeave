from contexts.base import ContextBuilder, SCORE_CLAMP


class BusinessContextBuilder(ContextBuilder):
    def ignore_income(self) -> bool:
        return False

    def primary_metrics(self) -> list[str]:
        return ["market_size", "competition", "funding_access", "success_rate"]

    def build_anchors(self, data: dict) -> dict:
        return {
            "market_size_score": data.get("market_size_score", 65),
            "competition_intensity": data.get("competition_intensity", 50),
            "funding_availability": data.get("funding_availability", 55),
            "failure_rate_5yr": data.get("failure_rate_5yr", 50),
            "profitability_timeline_years": data.get("profitability_timeline_years", 3),
            "regulatory_difficulty": data.get("regulatory_difficulty", 40),
            "live_gdp_growth": data.get("live_gdp_growth"),
            "live_cpi": data.get("live_cpi"),
            "psychographic_bases": {"stress": 65, "health": 55, "relationships": 50, "happiness": 58},
        }

    def build_initial_scores(self, data: dict) -> dict[str, dict[str, float]]:
        ms = data.get("market_size_score", 65)
        comp = data.get("competition_intensity", 50)
        funding = data.get("funding_availability", 55)
        return {
            "A": {
                "market_size": SCORE_CLAMP(ms - 5),
                "competition": SCORE_CLAMP(comp + 10),
                "funding_access": SCORE_CLAMP(funding - 8),
                "revenue_potential": SCORE_CLAMP(50),
                "stress": 60,
                "health": 65,
                "relationships": 58,
                "happiness": 55,
                "opportunity": SCORE_CLAMP(65),
            },
            "B": {
                "market_size": SCORE_CLAMP(ms + 5),
                "competition": SCORE_CLAMP(comp),
                "funding_access": SCORE_CLAMP(funding + 5),
                "revenue_potential": SCORE_CLAMP(60),
                "stress": 68,
                "health": 58,
                "relationships": 52,
                "happiness": 62,
                "opportunity": SCORE_CLAMP(75),
            },
            "C": {
                "market_size": SCORE_CLAMP(ms + 12),
                "competition": SCORE_CLAMP(comp - 8),
                "funding_access": SCORE_CLAMP(funding + 15),
                "revenue_potential": SCORE_CLAMP(72),
                "stress": 78,
                "health": 50,
                "relationships": 42,
                "happiness": 65,
                "opportunity": SCORE_CLAMP(85),
            },
        }
