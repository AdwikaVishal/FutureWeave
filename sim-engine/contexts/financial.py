from contexts.base import ContextBuilder, SCORE_CLAMP


class FinancialContextBuilder(ContextBuilder):
    def ignore_income(self) -> bool:
        return False

    def primary_metrics(self) -> list[str]:
        return ["interest_rate", "market_return", "inflation", "tax_efficiency"]

    def build_anchors(self, data: dict) -> dict:
        return {
            "interest_rate": data.get("interest_rate", 6.5),
            "market_return_expected": data.get("market_return_expected", 10.0),
            "inflation_rate": data.get("inflation_rate", 5.0),
            "tax_rate": data.get("tax_rate", 30.0),
            "risk_free_rate": data.get("risk_free_rate", 3.0),
            "real_estate_appreciation": data.get("real_estate_appreciation", 7.0),
            "live_cpi": data.get("live_cpi"),
            "live_gdp_growth": data.get("live_gdp_growth"),
            "psychographic_bases": {"stress": 50, "health": 60, "relationships": 55, "happiness": 58},
        }

    def build_initial_scores(self, data: dict) -> dict[str, dict[str, float]]:
        interest = data.get("interest_rate", 6.5)
        market = data.get("market_return_expected", 10.0)
        inflation = data.get("inflation_rate", 5.0)
        return {
            "A": {
                "income": SCORE_CLAMP(50),
                "financial_health": SCORE_CLAMP(65),
                "stress": 40,
                "health": 68,
                "relationships": 60,
                "happiness": 60,
                "opportunity": SCORE_CLAMP(55),
            },
            "B": {
                "income": SCORE_CLAMP(60),
                "financial_health": SCORE_CLAMP(70),
                "stress": 50,
                "health": 60,
                "relationships": 55,
                "happiness": 58,
                "opportunity": SCORE_CLAMP(65),
            },
            "C": {
                "income": SCORE_CLAMP(70),
                "financial_health": SCORE_CLAMP(75),
                "stress": 62,
                "health": 55,
                "relationships": 48,
                "happiness": 55,
                "opportunity": SCORE_CLAMP(72),
            },
        }
