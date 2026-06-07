import logging
from typing import Any, Optional

from deterministic_formulas import safe_lower

logger = logging.getLogger(__name__)


class RiskAgent:
    def __init__(self):
        self.name = "risk"

    def analyze(
        self,
        decision: str,
        context: dict,
        economic_data: dict,
        core_variables: Optional[dict] = None,
        memory_context: Optional[str] = None,
    ) -> dict:
        risk_raw = safe_lower(context.get("risk_tolerance", "moderate"))
        risk_map = {"low": 25, "moderate": 50, "high": 75}
        base = risk_map.get(risk_raw, 50)
        gdp = economic_data.get("gdp_growth", 6.0)
        unemp = economic_data.get("unemployment_rate", 5.0)
        economic_risk_mod = 0
        if gdp is not None and gdp < 4:
            economic_risk_mod = +10
        if unemp is not None and unemp > 8:
            economic_risk_mod += +10
        score = min(100, max(0, base + economic_risk_mod))
        confidence = round(0.6 + (1.0 - abs(base - 50) / 50) * 0.3, 2)
        return {
            "score": score,
            "reasoning": f"Risk assessment based on {risk_raw} tolerance profile "
                         f"with economic conditions (GDP={gdp}, unemployment={unemp}) contributing {economic_risk_mod:+d} pts.",
            "confidence": confidence,
            "agent_name": self.name,
            "source_attribution": [
                {"factor": "Risk Tolerance", "value": risk_raw, "contribution": f"{base} base score"},
                {"factor": "GDP Growth", "value": gdp, "contribution": f"{'+10' if gdp < 4 else '0'} pts"},
                {"factor": "Unemployment", "value": unemp, "contribution": f"{'+10' if unemp > 8 else '0'} pts"},
            ],
        }
