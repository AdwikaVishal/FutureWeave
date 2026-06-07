"""
Financial Agent — analyzes net worth, savings, debt, cash flow, investments.
"""
import json
import logging
from typing import Any, Dict, Optional

from .llm_agent import LLMAgent
from quota_manager import get_quota_manager
from deterministic_formulas import (
    compute_net_worth, compute_financial_risk,
)

logger = logging.getLogger(__name__)


class FinancialAgent(LLMAgent):
    def __init__(self):
        super().__init__("financial", "financial.txt", temperature=0.4)

    def analyze(
        self,
        decision: str,
        context: dict,
        economic_data: dict,
        core_variables: Optional[dict] = None,
        memory_context: Optional[str] = None,
    ) -> dict:
        if not isinstance(context, dict):
            logger.error("[FinancialAgent] context is not a dict: %s", type(context))
            context = {}
        if not isinstance(economic_data, dict):
            logger.error("[FinancialAgent] economic_data is not a dict: %s", type(economic_data))
            economic_data = {}
        qm = get_quota_manager()
        cvars = core_variables if isinstance(core_variables, dict) else {}

        if not qm.should_use_llm("financial"):
            logger.info("[FinancialAgent] Quota mode '%s' — using deterministic formulas", qm.mode)
            return self._deterministic(context, economic_data, cvars)

        prompt = self.build_prompt(
            decision=decision,
            context=json.dumps(context, indent=2, default=str),
            gdp_growth=economic_data.get("gdp_growth", 6.49),
            inflation_cpi=economic_data.get("inflation_cpi", 4.95),
            interest_rate=economic_data.get("interest_rate", 6.5),
            salary_growth_pct=economic_data.get("salary_growth_pct", 7.5),
            expected_salary_lpa=cvars.get("expected_salary_lpa", 9.5),
            monthly_income=cvars.get("monthly_income", 79000),
            monthly_expenses=cvars.get("monthly_expenses", 44000),
            disposable_income=cvars.get("disposable_income", 35000),
            savings_rate=cvars.get("savings_rate_pct", 44.3),
            risk_profile=context.get("risk_tolerance", "moderate"),
            memory_context=memory_context or "No prior context available.",
        )

        try:
            result = self.run_structured(prompt)
            self._validate(result)
            return result
        except Exception as exc:
            logger.warning("[FinancialAgent] LLM failed: %s — using deterministic", exc)
            return self._deterministic(context, economic_data, cvars)

    def _validate(self, result: dict):
        for key in ["net_worth_forecast", "wealth_growth_score", "financial_risk_score", "key_insights", "confidence"]:
            if key not in result:
                raise ValueError(f"Missing key: {key}")

    def _deterministic(self, context: dict, data: dict, cvars: dict) -> dict:
        profile = {}
        years = ["Year1", "Year3", "Year5", "Year7", "Year10"]
        salary_lpa = cvars.get("expected_salary_lpa", 9.5)
        disposable = cvars.get("disposable_income", 35000)
        savings_rate = cvars.get("savings_rate_pct", 44.3)

        net_worth = [compute_net_worth(profile, context, data, y, salary_lpa, disposable, savings_rate) for y in years]
        risk_scores = [compute_financial_risk(profile, context, data, y) for y in years]

        wealth_growth = round(sum(n["amount"] for n in net_worth) / len(net_worth) / 100_000, 1)
        fin_risk_avg = sum(r["score"] for r in risk_scores) / len(risk_scores)
        confidence = 0.70 - (fin_risk_avg / 100.0) * 0.2

        income_raw = salary_lpa
        income_score = round(min(100, income_raw * 8), 1)

        return {
            "income_raw": income_raw,
            "income_score": income_score,
            "net_worth_forecast": net_worth,
            "savings_trajectory": {
                "year1": net_worth[0]["amount"],
                "year3": net_worth[1]["amount"],
                "year5": net_worth[2]["amount"],
                "year7": net_worth[3]["amount"],
                "year10": net_worth[4]["amount"],
            },
            "debt_projection": {
                "has_debt": context.get("financial_condition", "stable") == "in_debt",
                "amount": 500000 if context.get("financial_condition") == "in_debt" else 0,
                "years_to_clear": 3 if context.get("financial_condition") == "in_debt" else 0,
            },
            "investment_outlook": {
                "expected_return": data.get("interest_rate", 6.5) + 2.0,
                "diversification_score": round(50 + (100 - int(data.get("automation_risk", 15))) * 0.2, 1),
                "narrative": "Moderate diversification with 60% equity, 30% debt, 10% alternatives balanced for risk profile.",
            },
            "wealth_growth_score": round(wealth_growth, 1),
            "financial_risk_score": round(fin_risk_avg, 1),
            "key_insights": [
                f"Savings rate of {savings_rate}% enables significant wealth accumulation over the decade.",
                f"Net worth trajectory shows {abs(net_worth[4]['amount'] - net_worth[0]['amount']):,}x growth from Year1 to Year10.",
                f"Income growth through career progression will accelerate wealth building in Years 3-7.",
                f"Financial risk score of {round(fin_risk_avg, 1)}/100 indicates {'low' if fin_risk_avg < 35 else 'moderate' if fin_risk_avg < 55 else 'elevated'} risk exposure.",
            ],
            "confidence": round(min(confidence, 0.92), 2),
        }
