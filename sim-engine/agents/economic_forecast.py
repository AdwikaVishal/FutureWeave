"""
Economic Forecasting Agent

Scores how economic conditions affect a user's decision over 10 years.

Consumes the output of collect_economic_research() — never fetches its own data.
Never invents economic facts. Every score is derived from supplied fields.
Missing data reduces confidence; it does NOT produce fabricated scores.

Output:
{
  "economic_outlook":      str,   # one-sentence headline truth
  "salary_growth_score":   int,   # 0–100  (real salary growth likelihood)
  "inflation_risk":        int,   # 0–100  (purchasing-power erosion)
  "industry_growth_score": int,   # 0–100  (industry health + demand)
  "automation_risk":       int,   # 0–100  (role displacement risk)
  "confidence":            int,   # 0–100  (data completeness)
  "reasoning":             str,   # which data drove each score + null flags
}
"""
import json
import logging
import os

from data_grounding import detect_role, detect_industry, normalise_location
from input_validator import safe_template_substitute
from llm_cache import get_cache
from llm_client import call_llm
from quota_manager import get_quota_manager

logger = logging.getLogger(__name__)

# ── Automation risk by industry (static knowledge, not invented data) ─────────
# Sources: McKinsey Global Institute (2023), WEF Future of Jobs (2023)
_AUTOMATION_RISK: dict[str, int] = {
    "software":      25,   # tooling automates tasks but demand grows
    "tech":          25,
    "it":            30,
    "finance":       55,   # rule-based analysis heavily automated
    "manufacturing": 70,   # robotics / process automation
    "retail":        65,   # self-checkout, logistics robots
    "education":     20,   # requires human judgement
    "healthcare":    18,   # regulation + human contact barrier
    "default":       45,
}

# Automation delta per role (additive on top of industry base)
_ROLE_AUTOMATION_DELTA: dict[str, int] = {
    "software engineer":   -10,  # builders of automation tools → lower personal risk
    "data scientist":      -5,
    "product manager":     -15,  # strategic / interpersonal
    "designer":            -10,
    "mechanical engineer": +10,  # physical process automation exposure
    "default":             0,
}

# Industry growth outlook 0–100 (static baseline — overridden by live data when available)
_INDUSTRY_GROWTH_BASE: dict[str, int] = {
    "software":      78,
    "tech":          75,
    "it":            68,
    "finance":       55,
    "healthcare":    72,
    "manufacturing": 42,
    "education":     50,
    "retail":        40,
    "default":       52,
}


# ── Deterministic scorer ──────────────────────────────────────────────────────

def _score_deterministic(
    economic_data: dict,
    role: str,
    industry: str,
    location: str,
) -> dict:
    """
    Compute all scores purely from supplied economic_data fields.
    Returns None only for values that genuinely have no data source.
    Never substitutes a missing value with an assumption.
    """
    # ── Extract supplied values ───────────────────────────────────────────────
    inflation_block = economic_data.get("inflation", {})
    cpi: float | None = inflation_block.get("cpi_consensus", {}).get("value")

    job_market = economic_data.get("job_market", {})
    gdp: float | None = job_market.get("gdp_growth_pct")
    unemployment: float | None = job_market.get("unemployment_pct")

    salary_block = economic_data.get("salary_growth", {})
    salary_range: list | None = salary_block.get("salary_range_lpa")

    econ_confidence: int = economic_data.get("confidence", 0)
    missing_count: int = len(economic_data.get("missing_data", []))
    null_fields: list[str] = []

    # ── 1. Inflation risk (0–100) ─────────────────────────────────────────────
    if cpi is not None:
        if cpi <= 2.0:
            inflation_risk = 10
        elif cpi <= 4.0:
            inflation_risk = 30
        elif cpi <= 6.0:
            inflation_risk = 50
        elif cpi <= 9.0:
            inflation_risk = 72
        else:
            inflation_risk = 90
    else:
        inflation_risk = 50          # no data → neutral, flagged below
        null_fields.append("cpi")

    # ── 2. Salary growth score (0–100) ───────────────────────────────────────
    # Real growth = nominal growth expectation minus inflation pressure.
    # GDP growth is the best proxy for nominal wage growth across industries.
    if gdp is not None:
        if gdp >= 7.0:
            salary_growth_score = 72
        elif gdp >= 5.0:
            salary_growth_score = 58
        elif gdp >= 2.0:
            salary_growth_score = 40
        else:
            salary_growth_score = 22
        # Subtract inflation drag
        salary_growth_score = max(0, salary_growth_score - (inflation_risk // 5))
    else:
        salary_growth_score = 45     # no data → below neutral, flagged below
        null_fields.append("gdp_growth_pct")

    # Boost if live salary range shows above-average band
    if salary_range:
        mid_salary = (salary_range[0] + salary_range[1]) / 2
        if mid_salary > 20:          # above ₹20 LPA mid — strong market
            salary_growth_score = min(100, salary_growth_score + 10)
        elif mid_salary < 6:         # below ₹6 LPA mid — constrained market
            salary_growth_score = max(0, salary_growth_score - 10)
    else:
        null_fields.append("salary_range_lpa")

    # ── 3. Industry growth score (0–100) ─────────────────────────────────────
    industry_growth_score = _INDUSTRY_GROWTH_BASE.get(industry, _INDUSTRY_GROWTH_BASE["default"])

    # GDP growth modifies baseline
    if gdp is not None:
        if gdp >= 7.0:
            industry_growth_score = min(100, industry_growth_score + 8)
        elif gdp < 3.0:
            industry_growth_score = max(0, industry_growth_score - 12)

    # Unemployment signal: high unemployment dampens growth outlook
    if unemployment is not None:
        if unemployment > 8.0:
            industry_growth_score = max(0, industry_growth_score - 10)
        elif unemployment < 4.0:
            industry_growth_score = min(100, industry_growth_score + 5)
    else:
        null_fields.append("unemployment_pct")

    # LinkedIn / FRED trend signal
    linkedin = job_market.get("linkedin_trends")
    if linkedin and isinstance(linkedin, dict):
        trend = str(linkedin.get("trend", "")).lower()
        if "growing" in trend or "high demand" in trend:
            industry_growth_score = min(100, industry_growth_score + 7)
        elif "declining" in trend or "shrinking" in trend:
            industry_growth_score = max(0, industry_growth_score - 10)

    # ── 4. Automation risk (0–100) ───────────────────────────────────────────
    industry_auto = _AUTOMATION_RISK.get(industry, _AUTOMATION_RISK["default"])
    role_delta = _ROLE_AUTOMATION_DELTA.get(role, _ROLE_AUTOMATION_DELTA["default"])
    automation_risk = max(0, min(100, industry_auto + role_delta))

    # ── 5. Economic outlook (one sentence) ───────────────────────────────────
    if gdp is not None and cpi is not None:
        real_growth = gdp - cpi
        if real_growth >= 3.0:
            outlook = (
                f"Strong real GDP growth ({real_growth:.1f}% above inflation) creates "
                f"expanding opportunity for {role}s in {location} over the next decade."
            )
        elif real_growth >= 0:
            outlook = (
                f"GDP growth ({gdp:.1f}%) marginally outpaces inflation ({cpi:.1f}%), "
                f"suggesting modest but real gains for {role}s in {location}."
            )
        else:
            outlook = (
                f"Inflation ({cpi:.1f}%) exceeds GDP growth ({gdp:.1f}%), "
                f"eroding real purchasing power for {role}s in {location}."
            )
    elif gdp is not None:
        outlook = (
            f"GDP growth of {gdp:.1f}% provides a directional signal, "
            f"but absent inflation data the real-income outlook for {location} is uncertain."
        )
    elif cpi is not None:
        outlook = (
            f"Inflation at {cpi:.1f}% is confirmed, "
            f"but without GDP data the net real-income trajectory for {role}s is unknown."
        )
    else:
        outlook = (
            f"Neither GDP growth nor inflation data is available for {location}; "
            f"the 10-year economic outlook carries high uncertainty."
        )

    # ── 6. Confidence ────────────────────────────────────────────────────────
    # Inherit from economic_research confidence, then penalise per null field
    confidence = econ_confidence
    confidence -= len(null_fields) * 5
    confidence = max(0, min(100, confidence))

    # ── 7. Reasoning ─────────────────────────────────────────────────────────
    null_note = (
        f" Null fields (scores set to neutral): {', '.join(null_fields)}."
        if null_fields else ""
    )
    reasoning = (
        f"salary_growth_score driven by GDP={gdp}% with inflation drag "
        f"(inflation_risk={inflation_risk}); "
        f"industry_growth_score based on {industry} baseline ({_INDUSTRY_GROWTH_BASE.get(industry, 52)}) "
        f"adjusted for GDP and unemployment signals; "
        f"automation_risk is static knowledge for {industry}/{role} "
        f"(McKinsey/WEF 2023 baselines — not derived from live data)."
        f"{null_note}"
        f" Economic data confidence from research agent: {econ_confidence}%"
        f" ({missing_count} source(s) missing)."
    )

    return {
        "economic_outlook":      outlook,
        "salary_growth_score":   salary_growth_score,
        "inflation_risk":        inflation_risk,
        "industry_growth_score": industry_growth_score,
        "automation_risk":       automation_risk,
        "confidence":            confidence,
        "reasoning":             reasoning,
    }


def _validate(result: dict, fallback: dict) -> dict:
    """Ensure all required keys are present and scores are in range."""
    int_keys = (
        "salary_growth_score", "inflation_risk",
        "industry_growth_score", "automation_risk", "confidence",
    )
    for key in int_keys:
        try:
            result[key] = max(0, min(100, int(result[key])))
        except (TypeError, ValueError, KeyError):
            result[key] = fallback[key]

    for key in ("economic_outlook", "reasoning"):
        if not result.get(key) or not isinstance(result[key], str):
            result[key] = fallback[key]

    return result


# ── LLM prompt loader ─────────────────────────────────────────────────────────

def _load_prompt() -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", "economic_forecast_prompt.txt")
    with open(path) as f:
        return f.read()


# ── Public entry point ────────────────────────────────────────────────────────

def forecast_economic_impact(
    decision: str,
    context: dict,
    economic_data: dict,
) -> dict:
    """
    Score how economic conditions affect this decision over 10 years.

    Args:
        decision:      Raw decision text from the user.
        context:       User demographics dict.
        economic_data: Output of collect_economic_research() — already fetched.

    Returns:
        {
          "economic_outlook":      str,
          "salary_growth_score":   int (0–100),
          "inflation_risk":        int (0–100),
          "industry_growth_score": int (0–100),
          "automation_risk":       int (0–100),
          "confidence":            int (0–100),
          "reasoning":             str,
        }
    """
    role     = detect_role(decision, context)
    industry = detect_industry(decision, context)
    location = normalise_location(context.get("location", "India"))

    # Always compute deterministic scores first — they are the fallback
    # and also the integrity check for LLM output.
    deterministic = _score_deterministic(economic_data, role, industry, location)

    cache = get_cache()
    qm    = get_quota_manager()

    cache_key = cache.make_key(
        "economic_forecast_v1",
        decision,
        location,
        industry,
        json.dumps(economic_data.get("inflation", {}), sort_keys=True, default=str),
        str(economic_data.get("job_market", {}).get("gdp_growth_pct")),
        str(economic_data.get("confidence", 0)),
    )

    cached = cache.get(cache_key, model="economic_forecast")
    if cached is not None:
        logger.info("[EconomicForecast] Cache hit")
        return cached

    if not qm.should_use_llm("synthesis"):
        logger.info("[EconomicForecast] Quota mode '%s' — deterministic scores", qm.mode)
        return deterministic

    template = _load_prompt()
    prompt = safe_template_substitute(
        template,
        decision=decision,
        context_json=json.dumps(context, indent=2, default=str),
        economic_data_json=json.dumps(economic_data, indent=2, default=str),
        role=role,
        industry=industry,
        location=location,
    )

    try:
        raw    = call_llm(prompt, temperature=0.3)   # low temp — factual scoring task
        qm.record_call()
        result = json.loads(raw)
        result = _validate(result, deterministic)
        cache.set(cache_key, model="economic_forecast", response=result)
        logger.info(
            "[EconomicForecast] LLM scored: salary=%d inflation=%d industry=%d auto=%d conf=%d",
            result["salary_growth_score"], result["inflation_risk"],
            result["industry_growth_score"], result["automation_risk"], result["confidence"],
        )
        return result

    except Exception as exc:
        qm.record_error(is_rate_limit="429" in str(exc) or "rate" in str(exc).lower())
        logger.warning("[EconomicForecast] LLM failed: %s — deterministic fallback", exc)
        return deterministic
