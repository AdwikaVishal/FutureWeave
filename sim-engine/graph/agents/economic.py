"""
Economic Agent — analyzes macro-economic factors for the simulation.
"""
import json
import logging
from typing import Any, Dict, Optional

from .llm_agent import LLMAgent
from quota_manager import get_quota_manager
from deterministic_formulas import compute_gdp_forecast, compute_salary_growth_forecast

logger = logging.getLogger(__name__)


class EconomicAgent(LLMAgent):
    def __init__(self):
        super().__init__("economic", "economic.txt", temperature=0.3)

    def analyze(
        self,
        decision: str,
        context: dict,
        economic_data: dict,
        core_variables: Optional[dict] = None,
        memory_context: Optional[str] = None,
    ) -> dict:
        if not isinstance(context, dict):
            logger.error("[EconomicAgent] context is not a dict: %s", type(context))
            context = {}
        if not isinstance(economic_data, dict):
            logger.error("[EconomicAgent] economic_data is not a dict: %s", type(economic_data))
            economic_data = {}
        qm = get_quota_manager()
        cvars = core_variables if isinstance(core_variables, dict) else {}

        if not qm.should_use_llm("economic"):
            logger.info("[EconomicAgent] Quota mode '%s' — using deterministic formulas", qm.mode)
            return self._deterministic(context, economic_data)

        prompt = self.build_prompt(
            decision=decision,
            context=json.dumps(context, indent=2, default=str),
            gdp_growth=economic_data.get("gdp_growth", 6.49),
            inflation_cpi=economic_data.get("inflation_cpi", 4.95),
            interest_rate=economic_data.get("interest_rate", 6.5),
            salary_growth_pct=economic_data.get("salary_growth_pct", 7.5),
            industry_growth_rate=economic_data.get("industry_growth_rate", 8.0),
            industry=context.get("industry", "technology"),
            location=context.get("location", "Bangalore"),
            memory_context=memory_context or "No prior context available.",
        )

        try:
            result = self.run_structured(prompt)
            self._validate(result)
            return result
        except Exception as exc:
            logger.warning("[EconomicAgent] LLM failed: %s — using deterministic", exc)
            return self._deterministic(context, economic_data)

    def _validate(self, result: dict):
        for key in ["gdp_forecast", "salary_growth_forecast", "industry_health_forecast", "economic_confidence_index", "confidence"]:
            if key not in result:
                raise ValueError(f"Missing key: {key}")

    def _deterministic(self, context: dict, data: dict) -> dict:
        profile = {}
        if not isinstance(data, dict):
            logger.error("[EconomicAgent] _deterministic received non-dict data: %s", type(data))
            data = {}
        years = ["Year1", "Year3", "Year5", "Year7", "Year10"]

        gdp = compute_gdp_forecast(data)
        salary = compute_salary_growth_forecast(profile, context, data)

        inflation = data.get("inflation_cpi", 4.95) if isinstance(data, dict) else 4.95
        interest_rate = data.get("interest_rate", 6.5) if isinstance(data, dict) else 6.5

        first_gdp_value = gdp[0]["value"] if gdp and isinstance(gdp, list) and len(gdp) > 0 and isinstance(gdp[0], dict) else 6.49

        return {
            "gdp_forecast": gdp,
            "inflation_forecast": [
                {"year": y, "cpi": round(max(2.0, inflation * (1 - 0.03 * i)), 1),
                 "narrative": "Inflation remains a concern but within RBI tolerance band." if i == 0
                 else "Inflation moderates as supply chains stabilize." if i == 1
                 else "Structural reforms keep inflation in check." if i == 2
                 else "Inflation near target — stable macroeconomic management." if i == 3
                 else "Long-term inflation anchored by credible monetary policy."}
                for i, y in enumerate(years)
            ],
            "interest_rate_forecast": [
                {"year": y, "rate": round(max(3.0, interest_rate * (1 - 0.02 * i)), 1),
                 "narrative": "Current rate cycle reflecting inflation management." if i == 0
                 else "Rates ease as inflation moderates." if i == 1
                 else "Accommodative monetary policy supports growth." if i == 2
                 else "Rates stabilize at long-term equilibrium." if i == 3
                 else "Structural low-rate environment for mature economy."}
                for i, y in enumerate(years)
            ],
            "salary_growth_forecast": salary,
            "industry_health_forecast": [
                {"year": y, "score": round(70 + 3 * i + (data.get("industry_growth_rate", 8.0) - 5) * 1.5, 1),
                 "narrative": n}
                for i, (y, n) in enumerate([
                    ("Year1", "Industry is healthy with strong demand for talent."),
                    ("Year3", "Industry expands — new sub-sectors emerge creating opportunities."),
                    ("Year5", "Maturity brings both stability and consolidation opportunities."),
                    ("Year7", "Established industry with innovation driving continued growth."),
                    ("Year10", "Industry is a major economic pillar with diverse career paths."),
                ])
            ],
            "economic_confidence_index": round(60 + first_gdp_value * 2, 1),
            "key_insights": [
                "India's demographic dividend provides a 20+ year growth runway.",
                "Your industry is well-positioned to benefit from digital transformation tailwinds.",
                f"Salary growth trajectories indicate real income gains through Year7 before normalization.",
                "Consider inflation-indexed investments to protect purchasing power.",
            ],
            "confidence": round(0.65 + (first_gdp_value / 10.0) * 0.2, 2),
        }
