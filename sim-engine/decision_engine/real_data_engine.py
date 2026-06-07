from __future__ import annotations
import math
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RealDataScores:
    economic_score: float = 50.0
    employment_score: float = 50.0
    industry_score: float = 50.0
    cost_of_living_score: float = 50.0
    salary_score: float = 50.0
    confidence: float = 50.0
    data_freshness: Dict[str, str] = field(default_factory=dict)
    data_completeness: float = 1.0
    data_sources_used: List[str] = field(default_factory=list)
    breakdown: Dict[str, Any] = field(default_factory=dict)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def compute_real_data_scores(economic: Any, profile: Any, grounding: Dict[str, Any]) -> RealDataScores:
    data_sources = []
    freshness = {}
    weights_used = {}

    gdp = getattr(economic, "gdp_growth", None)
    inflation = getattr(economic, "inflation_cpi", None)
    unemployment = getattr(economic, "unemployment_rate", None)
    salary_growth = getattr(economic, "salary_growth_pct", None)
    industry_health = getattr(economic, "industry_health", None)
    col_index = getattr(economic, "cost_of_living_index", 1.0)
    automation_risk = getattr(economic, "automation_risk", None)
    interest_rate = getattr(economic, "interest_rate", None)
    data_conf = getattr(economic, "data_confidence", 0.85)

    salary_entry = grounding.get("salary_entry_lpa", (3, 6))
    salary_mid = grounding.get("salary_mid_lpa", (7, 15))
    salary_senior = grounding.get("salary_senior_lpa", (15, 35))
    avg_salary = (salary_entry[0] + salary_entry[1] + salary_mid[0] + salary_mid[1]) / 4.0

    live_salary = grounding.get("live_salary_range")
    live_cpi = grounding.get("live_cpi")
    live_unemployment = grounding.get("live_unemployment")
    live_gdp = grounding.get("live_gdp_growth")
    col_source = grounding.get("cost_of_living_source", "static")
    salary_source = grounding.get("salary_source", "static")
    worldbank_sources = grounding.get("worldbank_sources", {})

    if live_gdp is not None:
        gdp = live_gdp
        data_sources.append("World Bank GDP Growth")
        freshness["gdp_growth"] = "live"
    else:
        freshness["gdp_growth"] = "static_estimate"

    if live_cpi is not None:
        inflation = live_cpi
        data_sources.append(f"World Bank/CPI Inflation")
        freshness["inflation_cpi"] = "live"
    else:
        freshness["inflation_cpi"] = "static_estimate"

    if live_unemployment is not None:
        unemployment = live_unemployment
        data_sources.append("World Bank Unemployment")
        freshness["unemployment_rate"] = "live"
    else:
        freshness["unemployment_rate"] = "static_estimate"

    if live_salary:
        data_sources.append(f"{salary_source} Salary Data")
        freshness["salary"] = "live"
    else:
        freshness["salary"] = "static_estimate"

    if col_source != "static":
        data_sources.append(f"{col_source} Cost of Living")
        freshness["cost_of_living"] = "live"
    else:
        freshness["cost_of_living"] = "static_estimate"

    live_count = sum(1 for v in freshness.values() if v == "live")
    total_count = len(freshness)
    data_completeness = live_count / max(total_count, 1)

    gdp = gdp if gdp is not None else 6.5
    inflation = inflation if inflation is not None else 5.0
    unemployment = unemployment if unemployment is not None else 4.2
    salary_growth = salary_growth if salary_growth is not None else 7.5
    industry_health = industry_health if industry_health is not None else 78.0
    automation_risk = automation_risk if automation_risk is not None else 15.0

    economic_score = _compute_economic_strength(gdp, inflation, unemployment, interest_rate or 6.5)
    employment_score = _compute_employment_score(unemployment, industry_health, automation_risk)
    industry_score = _compute_industry_growth(industry_health, gdp, automation_risk)
    cost_of_living_score = _compute_col_score(col_index, inflation)
    salary_score = _compute_salary_opportunity(salary_growth, industry_health, col_index, live_salary, avg_salary)

    source_confidence = data_conf * 100
    completeness_factor = data_completeness
    confidence = _clamp(source_confidence * (0.6 + 0.4 * completeness_factor))

    breakdown = {
        "economic_strength": {
            "score": round(economic_score, 1),
            "gdp_contribution": round(_clamp(gdp / 10.0 * 40), 1),
            "inflation_penalty": round(_clamp(max(0, inflation - 4) * 3), 1),
            "unemployment_penalty": round(_clamp(unemployment / 10.0 * 25), 1),
            "interest_rate_contribution": round(_clamp((5.0 / max(interest_rate or 6.5, 1)) * 15), 1),
        },
        "employment": {
            "score": round(employment_score, 1),
            "unemployment_rate": round(unemployment, 1),
            "industry_health": round(industry_health, 1),
            "automation_risk": round(automation_risk, 1),
        },
        "industry_growth": {
            "score": round(industry_score, 1),
            "industry_health": round(industry_health, 1),
            "gdp_tailwind": round(_clamp(gdp / 10.0 * 30), 1),
            "automation_headwind": round(_clamp(automation_risk / 50.0 * 20), 1),
        },
        "cost_of_living": {
            "score": round(cost_of_living_score, 1),
            "col_index": round(col_index, 2),
            "inflation_adjustment": round(_clamp(max(0, inflation - 4) * 2), 1),
        },
        "salary_opportunity": {
            "score": round(salary_score, 1),
            "salary_growth": round(salary_growth, 1),
            "industry_demand": round(industry_health / 100.0 * 30, 1),
            "col_adjustment": round(_clamp((1.0 / col_index) * 15), 1),
        },
    }

    logger.info("[RealDataEngine] Scores: economic=%.1f employment=%.1f col=%.1f salary=%.1f confidence=%.1f",
                economic_score, employment_score, cost_of_living_score, salary_score, confidence)
    logger.info("[RealDataEngine] Data sources: %s", data_sources)
    logger.info("[RealDataEngine] Freshness: %s", freshness)
    logger.info("[RealDataEngine] Breakdown: %s", breakdown)

    return RealDataScores(
        economic_score=round(economic_score, 1),
        employment_score=round(employment_score, 1),
        industry_score=round(industry_score, 1),
        cost_of_living_score=round(cost_of_living_score, 1),
        salary_score=round(salary_score, 1),
        confidence=round(confidence, 1),
        data_freshness=freshness,
        data_completeness=round(data_completeness, 2),
        data_sources_used=data_sources,
        breakdown=breakdown,
    )


def _compute_economic_strength(gdp: float, inflation: float, unemployment: float, interest_rate: float) -> float:
    gdp_component = _clamp(gdp / 10.0 * 40, 0, 40)
    inflation_penalty = _clamp(max(0, inflation - 4) * 3, 0, 30)
    unemployment_penalty = _clamp(unemployment / 10.0 * 25, 0, 25)
    interest_component = _clamp((5.0 / max(interest_rate, 1)) * 15, 0, 15)
    score = gdp_component + interest_component - inflation_penalty - unemployment_penalty
    return _clamp(score + 20)


def _compute_employment_score(unemployment: float, industry_health: float, automation_risk: float) -> float:
    base = _clamp(100 - unemployment * 3, 20, 80)
    industry_boost = _clamp((industry_health - 50) / 50.0 * 15, -15, 15)
    automation_penalty = _clamp(automation_risk / 50.0 * 10, 0, 10)
    return _clamp(base + industry_boost - automation_penalty)


def _compute_industry_growth(industry_health: float, gdp: float, automation_risk: float) -> float:
    base = industry_health * 0.6
    gdp_tailwind = _clamp(gdp / 10.0 * 30, 0, 30)
    automation_headwind = _clamp(automation_risk / 50.0 * 20, 0, 20)
    return _clamp(base + gdp_tailwind - automation_headwind)


def _compute_col_score(col_index: float, inflation: float) -> float:
    base = _clamp((1.0 / col_index) * 60, 20, 60)
    inflation_penalty = _clamp(max(0, inflation - 4) * 2, 0, 20)
    return _clamp(base - inflation_penalty + 20)


def _compute_salary_opportunity(salary_growth: float, industry_health: float, col_index: float, live_salary: Optional[List[float]], avg_salary: float) -> float:
    growth_component = _clamp(salary_growth / 15.0 * 25, 0, 25)
    demand_component = _clamp(industry_health / 100.0 * 20, 0, 20)
    col_adjustment = _clamp((1.0 / col_index) * 10, 0, 10)
    live_data_bonus = 5 if live_salary else 0
    salary_level_bonus = _clamp((avg_salary - 5) / 20.0 * 20, -10, 20)
    return _clamp(growth_component + demand_component + col_adjustment + live_data_bonus + salary_level_bonus + 25)
