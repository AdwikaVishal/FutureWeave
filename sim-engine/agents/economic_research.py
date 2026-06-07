"""
Economic Research Agent

Collects CURRENT economic data from up to 8 sources in parallel and returns
a structured report across 5 dimensions:

  salary_growth   — salary ranges + YoY growth from AmbitionBox + Glassdoor
  job_market      — open roles, trends from LinkedIn + FRED
  inflation       — CPI from World Bank + IMF + India Gov (MOSPI)
  cost_of_living  — Numbeo monthly cost baselines
  future_trends   — composite forward-looking view

Confidence score:
  Starts at 100.  Each unavailable source deducts its weight (see _WEIGHTS).
  If data cannot be found, it is NOT invented — the gap is recorded explicitly.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any

from services.common import ProviderResult, timed_provider
from services.ambitionbox import fetch_salary
from services.glassdoor import fetch_glassdoor_salary
from services.worldbank import fetch_worldbank
from services.imf import fetch_imf
from services.india_gov import fetch_india_gov_stats
from services.fred import fetch_industry_data
from services.linkedin import fetch_job_trends
from services.numbeo import fetch_cost_of_living
from data_grounding import detect_role, detect_industry, normalise_location

logger = logging.getLogger(__name__)

# ── Confidence weights per source (must sum to 100) ───────────────────────────
_WEIGHTS = {
    "worldbank":   15,
    "imf":         15,
    "ambitionbox": 15,
    "glassdoor":   10,
    "numbeo":      15,
    "india_gov":   10,
    "fred":        10,
    "linkedin":    10,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _gap(source: str, field: str, error: str | None, confidence: int, deduction: int) -> dict:
    return {
        "source": source,
        "field": field,
        "error": error or "unavailable",
        "confidence_deduction": deduction,
        "confidence_after": confidence,
    }


def _blend_salary(a: list[float] | None, b: list[float] | None) -> list[float] | None:
    """Average two salary ranges when both are available."""
    if a and b:
        return [round((a[0] + b[0]) / 2, 1), round((a[1] + b[1]) / 2, 1)]
    return a or b


def _cpi_consensus(wb: float | None, imf: float | None, gov: float | None) -> dict:
    """Return the best CPI estimate and note which sources agreed."""
    available = {k: v for k, v in [("world_bank", wb), ("imf", imf), ("india_gov", gov)] if v is not None}
    if not available:
        return {"value": None, "sources": [], "note": "No CPI data available from any source."}
    avg = round(sum(available.values()) / len(available), 2)
    return {
        "value": avg,
        "sources": list(available.keys()),
        "by_source": available,
        "note": f"Consensus across {len(available)} source(s).",
    }


# ── Main agent ─────────────────────────────────────────────────────────────────

async def collect_economic_research(
    decision: str,
    context: dict,
    *,
    country: str = "IN",
) -> dict:
    """
    Fan-out to all 8 data sources in parallel; assemble the 5-field report.

    Returns:
    {
      "salary_growth":    {...},
      "job_market":       {...},
      "inflation":        {...},
      "cost_of_living":   {...},
      "future_trends":    {...},
      "confidence":       int (0-100),
      "confidence_breakdown": [...],
      "missing_data":     [...],
      "collected_at":     ISO timestamp,
    }
    """
    role     = detect_role(decision, context)
    industry = detect_industry(decision, context)
    location = normalise_location(context.get("location", "India"))

    # ── Fan-out (all sources in parallel) ─────────────────────────────────────
    (
        r_worldbank,
        r_imf,
        r_ambitionbox,
        r_glassdoor,
        r_numbeo,
        r_india_gov,
        r_fred,
        r_linkedin,
    ) = await asyncio.gather(
        timed_provider("worldbank",   "macro",          lambda: fetch_worldbank(country)),
        timed_provider("imf",         "weo",            lambda: fetch_imf(country)),
        timed_provider("ambitionbox", "salary",         lambda: fetch_salary(role, location)),
        timed_provider("glassdoor",   "salary",         lambda: fetch_glassdoor_salary(role, location)),
        timed_provider("numbeo",      "cost_of_living", lambda: fetch_cost_of_living(location)),
        timed_provider("india_gov",   "mospi",          lambda: fetch_india_gov_stats()),
        timed_provider("fred",        "industry",       lambda: fetch_industry_data(industry)),
        timed_provider("linkedin",    "job_trends",     lambda: fetch_job_trends(role, location)),
        return_exceptions=False,
    )

    all_results: dict[str, ProviderResult] = {
        "worldbank":   r_worldbank,
        "imf":         r_imf,
        "ambitionbox": r_ambitionbox,
        "glassdoor":   r_glassdoor,
        "numbeo":      r_numbeo,
        "india_gov":   r_india_gov,
        "fred":        r_fred,
        "linkedin":    r_linkedin,
    }

    # ── Confidence scoring ────────────────────────────────────────────────────
    confidence = 100
    confidence_breakdown: list[dict] = []
    missing_data: list[dict] = []

    for source, result in all_results.items():
        weight = _WEIGHTS[source]
        if result.available:
            confidence_breakdown.append({
                "source": source,
                "available": True,
                "weight": weight,
                "note": f"{source} data available (+{weight}%)",
            })
        else:
            confidence -= weight
            confidence = max(0, confidence)
            gap = _gap(source, source, result.error, confidence, weight)
            missing_data.append(gap)
            confidence_breakdown.append({
                "source": source,
                "available": False,
                "weight": weight,
                "error": result.error,
                "note": f"{source} unavailable (-{weight}%). {result.error or 'No detail.'}",
            })

    # ── Extract values (never invent — use None when missing) ─────────────────

    # Salary
    amb_range: list | None = (
        r_ambitionbox.data.get("salary_range_lpa") if r_ambitionbox.available else None
    )
    gd_range: list | None = (
        r_glassdoor.data.get("salary_range_lpa") if r_glassdoor.available else None
    )
    blended_salary = _blend_salary(amb_range, gd_range)

    # Macro — World Bank
    wb_vals  = r_worldbank.data.get("values", {}) if r_worldbank.available else {}
    wb_years = r_worldbank.data.get("years", {})  if r_worldbank.available else {}

    # Macro — IMF
    imf_vals  = r_imf.data.get("values", {}) if r_imf.available else {}
    imf_years = r_imf.data.get("years", {})  if r_imf.available else {}

    # Macro — India Gov (MOSPI)
    gov_vals = r_india_gov.data.get("values", {}) if r_india_gov.available else {}

    # CPI consensus
    cpi_consensus = _cpi_consensus(
        wb_vals.get("inflation"),
        imf_vals.get("inflation"),
        gov_vals.get("cpi"),
    )

    # ── Build the 5-field report ───────────────────────────────────────────────

    # 1. Salary growth
    salary_growth: dict[str, Any] = {
        "role": role,
        "location": location,
        "salary_range_lpa": blended_salary,
        "sources": {},
        "missing": [],
    }
    if amb_range:
        salary_growth["sources"]["ambitionbox"] = {
            "range_lpa": amb_range,
            "url": r_ambitionbox.source_url,
            "cache_hit": r_ambitionbox.cache_hit,
        }
    else:
        salary_growth["missing"].append({
            "source": "ambitionbox",
            "error": r_ambitionbox.error,
        })
    if gd_range:
        salary_growth["sources"]["glassdoor"] = {
            "range_lpa": gd_range,
            "url": r_glassdoor.source_url,
            "cache_hit": r_glassdoor.cache_hit,
        }
    else:
        salary_growth["missing"].append({
            "source": "glassdoor",
            "error": r_glassdoor.error,
        })
    if blended_salary is None:
        salary_growth["note"] = (
            "No live salary data available. "
            "Consumers of this report should use static database fallback."
        )

    # 2. Job market
    job_market: dict[str, Any] = {
        "role": role,
        "industry": industry,
        "location": location,
        "unemployment_pct": wb_vals.get("unemployment") if wb_vals.get("unemployment") is not None else imf_vals.get("unemployment"),
        "unemployment_year": wb_years.get("unemployment") if wb_years.get("unemployment") is not None else imf_years.get("unemployment"),
        "unemployment_source": (
            "world_bank" if wb_vals.get("unemployment") is not None else
            "imf" if imf_vals.get("unemployment") is not None else None
        ),
        "gdp_growth_pct": wb_vals.get("gdp_growth") if wb_vals.get("gdp_growth") is not None else imf_vals.get("gdp_growth"),
        "gdp_growth_year": wb_years.get("gdp_growth") if wb_years.get("gdp_growth") is not None else imf_years.get("gdp_growth"),
        "labour_force": wb_vals.get("labour_force"),
        "linkedin_trends": r_linkedin.data if r_linkedin.available else None,
        "fred_industry": r_fred.data if r_fred.available else None,
        "missing": [],
    }
    if not r_linkedin.available:
        job_market["missing"].append({"source": "linkedin", "error": r_linkedin.error})
    if not r_fred.available:
        job_market["missing"].append({"source": "fred", "error": r_fred.error})
    if job_market["unemployment_pct"] is None:
        job_market["missing"].append({
            "source": "worldbank+imf",
            "error": "Unemployment rate unavailable from World Bank and IMF.",
        })

    # 3. Inflation
    inflation: dict[str, Any] = {
        "cpi_consensus": cpi_consensus,
        "by_source": {
            "world_bank": {
                "cpi_pct": wb_vals.get("inflation"),
                "year": wb_years.get("inflation"),
                "available": r_worldbank.available,
                "error": None if r_worldbank.available else r_worldbank.error,
            },
            "imf": {
                "cpi_pct": imf_vals.get("inflation"),
                "year": imf_years.get("inflation"),
                "available": r_imf.available,
                "error": None if r_imf.available else r_imf.error,
            },
            "india_gov_mospi": {
                "cpi_pct": gov_vals.get("cpi"),
                "year": gov_vals.get("cpi_year"),
                "available": r_india_gov.available,
                "error": None if r_india_gov.available else r_india_gov.error,
            },
        },
        "missing": [g for g in missing_data if g["source"] in ("worldbank", "imf", "india_gov")],
    }

    # 4. Cost of living
    cost_of_living: dict[str, Any] = {
        "location": location,
        "available": r_numbeo.available,
        "source": "numbeo",
        "source_url": r_numbeo.source_url,
        "data": r_numbeo.data if r_numbeo.available else None,
        "missing": (
            [{"source": "numbeo", "error": r_numbeo.error}]
            if not r_numbeo.available else []
        ),
        "note": (
            None if r_numbeo.available
            else "Numbeo cost-of-living data unavailable. "
                 "NUMBEO_API_KEY may not be configured."
        ),
    }

    # 5. Future trends — composite forward-looking view
    gdp  = job_market.get("gdp_growth_pct")
    cpi  = cpi_consensus.get("value")
    unemp = job_market.get("unemployment_pct")

    trend_signals: list[str] = []
    if gdp is not None:
        if gdp >= 7.0:
            trend_signals.append(f"Strong GDP growth ({gdp:.1f}%) suggests expanding job market.")
        elif gdp >= 5.0:
            trend_signals.append(f"Moderate GDP growth ({gdp:.1f}%) — stable outlook.")
        else:
            trend_signals.append(f"Weak GDP growth ({gdp:.1f}%) may suppress hiring.")
    else:
        trend_signals.append("GDP growth data unavailable — trend direction unknown.")

    if cpi is not None:
        if cpi > 6.0:
            trend_signals.append(f"Elevated inflation ({cpi:.1f}%) erodes real income gains.")
        elif cpi >= 3.0:
            trend_signals.append(f"Moderate inflation ({cpi:.1f}%) — purchasing power stable.")
        else:
            trend_signals.append(f"Low inflation ({cpi:.1f}%) improves real disposable income.")
    else:
        trend_signals.append("Inflation data unavailable — cost-pressure trend unknown.")

    if unemp is not None:
        if unemp < 5.0:
            trend_signals.append(f"Low unemployment ({unemp:.1f}%) — talent market is competitive.")
        elif unemp < 8.0:
            trend_signals.append(f"Moderate unemployment ({unemp:.1f}%) — balanced market.")
        else:
            trend_signals.append(f"High unemployment ({unemp:.1f}%) — job competition is elevated.")

    if blended_salary:
        trend_signals.append(
            f"Current market salary for {role} in {location}: "
            f"₹{blended_salary[0]}–{blended_salary[1]} LPA."
        )

    future_trends: dict[str, Any] = {
        "signals": trend_signals,
        "data_completeness_pct": confidence,
        "note": (
            "Trends are derived only from available data. "
            f"{len(missing_data)} source(s) unavailable — see missing_data."
            if missing_data else
            "All sources available — high confidence in trend signals."
        ),
    }

    logger.info(
        "[EconomicResearch] role=%s location=%s confidence=%s missing=%s",
        role, location, confidence, [g["source"] for g in missing_data],
    )

    return {
        "salary_growth":    salary_growth,
        "job_market":       job_market,
        "inflation":        inflation,
        "cost_of_living":   cost_of_living,
        "future_trends":    future_trends,
        "confidence":       confidence,
        "confidence_breakdown": confidence_breakdown,
        "missing_data":     missing_data,
        "collected_at":     datetime.utcnow().isoformat() + "Z",
    }
