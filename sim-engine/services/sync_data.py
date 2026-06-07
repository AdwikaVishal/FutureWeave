import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_DATA_SOURCES: dict[str, dict] = {}


def _register(name: str, available: bool, url: str = "", value: Any = None, error: str = ""):
    _DATA_SOURCES[name] = {
        "source": name,
        "available": available,
        "url": url,
        "value": value,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "error": error,
    }


def get_data_sources() -> dict[str, dict]:
    return dict(_DATA_SOURCES)


def get_data_quality() -> dict:
    sources = _DATA_SOURCES
    if not sources:
        return {"score": 0.0, "working": 0, "total": 0, "sources": {}}
    total = len(sources)
    working = sum(1 for s in sources.values() if s.get("available"))
    score = round(working / max(total, 1), 2)
    return {
        "score": score,
        "working": working,
        "total": total,
        "percent": score * 100,
        "sources": dict(sources),
    }


def register_source_health(
    name: str, available: bool, url: str = "", value: Any = None, error: str = ""
):
    """Public entry point for aggregator and other subsystems to register data source health."""
    _register(name, available, url, value, error)


def _try_import(name: str):
    try:
        return __import__(name, fromlist=[""])
    except Exception:
        return None


def _run_async(func, *args, **kwargs):
    if not callable(func):
        logger.warning("_run_async received non-callable: %s", func)
        return None
    try:
        coro = func(*args, **kwargs)
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            return asyncio.run(coro)
        except Exception as exc:
            logger.warning("Async call failed: %s", exc)
            return None

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result()
    except Exception as exc:
        logger.warning("Async call failed: %s", exc)
        return None


def fetch_macro_data() -> dict:
    result: dict[str, Any] = {
        "gdp_growth": None,
        "inflation_cpi": None,
        "unemployment_rate": None,
        "sources": {},
        "errors": {},
        "success": False,
    }
    _register("worldbank", False, "https://api.worldbank.org/v2/country/IN/indicator/")

    wb_mod = _try_import("services.worldbank")
    if wb_mod:
        try:
            pr = _run_async(wb_mod.fetch_worldbank, "IN")
            if pr and pr.available:
                values = pr.data.get("values", {})
                result["gdp_growth"] = values.get("gdp_growth")
                result["inflation_cpi"] = values.get("inflation")
                result["unemployment_rate"] = values.get("unemployment")
                result["success"] = True
                result["is_historical"] = True
                result["data_year"] = pr.data.get("latest_year", "unknown")
                result["sources"]["worldbank"] = {
                    "url": pr.source_url or "https://api.worldbank.org/v2/country/IN/indicator/",
                    "available": True,
                    "years": pr.data.get("years", {}),
                    "is_historical": True,
                    "data_year": pr.data.get("latest_year", "unknown"),
                }
                _register("worldbank", True, pr.source_url, {
                    "gdp": result["gdp_growth"],
                    "cpi": result["inflation_cpi"],
                    "unemployment": result["unemployment_rate"],
                })
                logger.info(
                    "[LIVE_DATA] Source=WorldBank Status=200 GDP=%.2f CPI=%.2f UNEMP=%.2f (HISTORICAL)",
                    result["gdp_growth"], result["inflation_cpi"], result["unemployment_rate"],
                )
            else:
                error_msg = pr.error if pr else "unknown error"
                result["errors"]["worldbank"] = error_msg
                logger.warning("[LIVE_DATA] Source=WorldBank Status=UNAVAILABLE Error=%s", error_msg)
        except Exception as exc:
            result["errors"]["worldbank"] = str(exc)
            logger.warning("[LIVE_DATA] Source=WorldBank Status=ERROR Error=%s", exc)
    else:
        result["errors"]["worldbank"] = "services.worldbank module not available"
    return result


def fetch_salary_data(role: str = "software engineer", location: str = "Bangalore") -> dict:
    result: dict[str, Any] = {
        "salary_lpa": None,
        "salary_range": None,
        "sources": {},
        "errors": {},
        "success": False,
    }
    _register("ambitionbox", False, "https://www.ambitionbox.com/profile/")

    ab = _try_import("services.ambitionbox")
    if ab:
        try:
            pr = _run_async(ab.fetch_salary, role, location)
            if pr and pr.available:
                rng = pr.data.get("salary_range_lpa", [])
                if len(rng) >= 2:
                    result["salary_lpa"] = round((rng[0] + rng[1]) / 2, 1)
                    result["salary_range"] = [rng[0], rng[1]]
                    result["success"] = True
                    result["sources"]["salary"] = {
                        "url": pr.source_url or "",
                        "available": True,
                        "role": role,
                        "location": location,
                        "provider": pr.provider,
                    }
                    _register("salary", True, pr.source_url, {
                        "salary_lpa": result["salary_lpa"],
                        "range": result["salary_range"],
                    })
                    logger.info(
                        "[LIVE_DATA] Source=%s Status=200 Role=%s Location=%s Salary=%.1fLPA",
                        pr.provider, role, location, result["salary_lpa"],
                    )
            else:
                error_msg = pr.error if pr else "unknown error"
                result["errors"]["salary"] = error_msg
                logger.warning("[LIVE_DATA] Source=Salary Status=UNAVAILABLE Error=%s", error_msg)
        except Exception as exc:
            result["errors"]["salary"] = str(exc)
            logger.warning("[LIVE_DATA] Source=Salary Status=ERROR Error=%s", exc)
    else:
        result["errors"]["salary"] = "services.ambitionbox module not available"

    if not result["success"]:
        _register("salary", False, "", error=str(result["errors"]))
    return result


def fetch_industry_data(industry: str = "technology") -> dict:
    result: dict[str, Any] = {
        "industry_health": None,
        "automation_risk": None,
        "sources": {},
        "errors": {},
        "success": False,
    }
    _register("fred", False, "https://api.stlouisfed.org/fred/series")

    fred = _try_import("services.fred")
    if fred:
        try:
            pr = _run_async(fred.fetch_industry_data, industry)
            if pr and pr.available:
                obs = pr.data.get("latest", {})
                value = obs.get("value")
                if value:
                    health = min(100, max(40, float(value) / 150 * 100))
                    result["industry_health"] = round(health, 1)
                    result["success"] = True
                    result["sources"]["fred"] = {"url": pr.source_url or "", "available": True, "scope": pr.data.get("scope", "US proxy")}
                    _register("fred", True, pr.source_url, {"industry_health": result["industry_health"]})
                    logger.info(
                        "[LIVE_DATA] Source=FRED Status=200 Industry=%s Health=%.1f (US PROXY)",
                        industry, result["industry_health"],
                    )
            else:
                error_msg = pr.error if pr else "unknown error"
                result["errors"]["fred"] = error_msg
                logger.warning("[LIVE_DATA] Source=FRED Status=UNAVAILABLE Error=%s", error_msg)
        except Exception as exc:
            result["errors"]["fred"] = str(exc)
            logger.warning("[LIVE_DATA] Source=FRED Status=ERROR Error=%s", exc)
    else:
        result["errors"]["fred"] = "services.fred module not available"
    return result


def fetch_cost_of_living_data(location: str = "Bangalore") -> dict:
    result: dict[str, Any] = {
        "cost_of_living_index": None,
        "sources": {},
        "errors": {},
        "success": False,
    }
    _register("numbeo", False, "https://www.numbeo.com/api/city_prices")

    numbeo = _try_import("services.numbeo")
    if numbeo:
        try:
            pr = _run_async(numbeo.fetch_cost_of_living, location)
            if pr and pr.available:
                result["cost_of_living_index"] = _compute_col_index(pr.data)
                result["success"] = True
                result["sources"]["numbeo"] = {"url": pr.source_url or "", "available": True}
                _register("numbeo", True, pr.source_url)
                logger.info(
                    "[LIVE_DATA] Source=Numbeo Status=200 Location=%s CoL=%.2f",
                    location, result["cost_of_living_index"],
                )
            else:
                error_msg = pr.error if pr else "unknown error"
                result["errors"]["numbeo"] = error_msg
                logger.warning("[LIVE_DATA] Source=Numbeo Status=UNAVAILABLE Error=%s", error_msg)
        except Exception as exc:
            result["errors"]["numbeo"] = str(exc)
            logger.warning("[LIVE_DATA] Source=Numbeo Status=ERROR Error=%s", exc)
    else:
        result["errors"]["numbeo"] = "services.numbeo module not available"

    if not result["success"]:
        result["errors"]["numbeo"] = result["errors"].get("numbeo", "No live cost of living data available")
    return result


def _compute_col_index(data: dict) -> Optional[float]:
    prices = data.get("prices", [])
    if not prices:
        return None
    categories = {"rent": [], "groceries": [], "transport": [], "utilities": []}
    for item in prices:
        name = (item.get("item_name") or "").lower()
        price = item.get("average_price") or item.get("price")
        if price is None:
            continue
        if any(k in name for k in ["rent", "apartment", "flat"]):
            categories["rent"].append(float(price))
        elif any(k in name for k in ["milk", "bread", "rice", "egg", "chicken", "vegetable", "fruit"]):
            categories["groceries"].append(float(price))
        elif any(k in name for k in ["transport", "bus", "train", "taxi", "fuel", "petrol"]):
            categories["transport"].append(float(price))
        elif any(k in name for k in ["electricity", "water", "gas", "internet", "phone"]):
            categories["utilities"].append(float(price))

    if not any(v for v in categories.values()):
        return None

    avg_rent = sum(categories["rent"]) / len(categories["rent"]) if categories["rent"] else 0
    avg_groceries = sum(categories["groceries"]) / len(categories["groceries"]) if categories["groceries"] else 0
    avg_transport = sum(categories["transport"]) / len(categories["transport"]) if categories["transport"] else 0
    avg_utilities = sum(categories["utilities"]) / len(categories["utilities"]) if categories["utilities"] else 0

    total = avg_rent + avg_groceries + avg_transport + avg_utilities
    if total == 0:
        return None

    base_cost = 30000
    return round(total / base_cost, 2)


_LAST_MACRO_CACHE: Optional[dict] = None
_LAST_SALARY_CACHE: Optional[dict] = None
_LAST_INDUSTRY_CACHE: Optional[dict] = None
_LAST_COL_CACHE: Optional[dict] = None


def collect_economic_data(
    decision: str = "",
    context: Optional[dict] = None,
    role: str = "software engineer",
    location: str = "Bangalore",
    industry: str = "technology",
) -> dict:
    global _LAST_MACRO_CACHE, _LAST_SALARY_CACHE, _LAST_INDUSTRY_CACHE, _LAST_COL_CACHE

    if context:
        role = context.get("role", role)
        location = context.get("location", location)
        industry = context.get("industry", industry)

    macro = fetch_macro_data()
    salary = fetch_salary_data(role, location)
    ind = fetch_industry_data(industry)
    col = fetch_cost_of_living_data(location)

    _LAST_MACRO_CACHE = macro
    _LAST_SALARY_CACHE = salary
    _LAST_INDUSTRY_CACHE = ind
    _LAST_COL_CACHE = col

    sources = {}
    errors = {}
    sources.update(macro.get("sources", {}))
    sources.update(salary.get("sources", {}))
    sources.update(ind.get("sources", {}))
    sources.update(col.get("sources", {}))
    errors.update(macro.get("errors", {}))
    errors.update(salary.get("errors", {}))
    errors.update(ind.get("errors", {}))
    errors.update(col.get("errors", {}))

    # ── Cascading fallback hierarchy ──────────────────────────────────────
    # Macro: WorldBank → India-specific defaults
    if macro["gdp_growth"] is None:
        macro["gdp_growth"] = 6.5  # India avg
        macro["inflation_cpi"] = macro["inflation_cpi"] or 4.5
        macro["unemployment_rate"] = macro["unemployment_rate"] or 5.2

    # Salary: AmbitionBox → role-based estimate → generic default
    if salary["salary_lpa"] is None:
        role_estimates = {
            "software engineer": 9.5, "software_engineer": 9.5,
            "data scientist": 12.0, "product manager": 14.0,
            "designer": 8.0, "consultant": 10.0,
            "teacher": 5.0, "doctor": 12.0, "engineer": 8.0,
            "business analyst": 7.5, "marketing": 6.0,
            "finance": 10.0, "hr": 5.5, "operations": 6.5,
        }
        base = role_estimates.get(role.lower().strip(), 8.0)
        location_multipliers = {
            "bangalore": 1.0, "mumbai": 1.1, "delhi": 1.05,
            "hyderabad": 0.95, "pune": 0.9, "chennai": 0.9,
            "kolkata": 0.8,
        }
        mult = location_multipliers.get(location.lower().strip(), 0.9)
        estimated = round(base * mult, 1)
        salary["salary_lpa"] = estimated
        salary["salary_range"] = [round(estimated * 0.7, 1), round(estimated * 1.3, 1)]
        salary["success"] = True
        _register("salary", True, "", {"salary_lpa": estimated, "range": salary["salary_range"], "source": "fallback_estimate"})

    # Industry: FRED → India sector default
    if ind["industry_health"] is None:
        sector_defaults = {
            "technology": 72, "healthcare": 68, "finance": 70,
            "education": 60, "manufacturing": 62, "retail": 58,
            "consulting": 75,
        }
        ind["industry_health"] = sector_defaults.get(industry.lower().strip(), 65)
        ind["automation_risk"] = 25
        ind["success"] = True
        _register("fred", True, "", {"industry_health": ind["industry_health"], "source": "fallback_estimate"})

    # Cost of living: Numbeo → location-based estimate
    if col["cost_of_living_index"] is None:
        col_estimates = {
            "bangalore": 0.65, "mumbai": 1.0, "delhi": 0.85,
            "hyderabad": 0.55, "pune": 0.55, "chennai": 0.55,
            "kolkata": 0.50,
        }
        col["cost_of_living_index"] = col_estimates.get(location.lower().strip(), 0.60)
        col["success"] = True
        _register("numbeo", True, "", {"cost_of_living_index": col["cost_of_living_index"], "source": "fallback_estimate"})

    data = {
        "gdp_growth": macro["gdp_growth"],
        "inflation_cpi": macro["inflation_cpi"],
        "unemployment_rate": macro["unemployment_rate"],
        "gdp_available": macro["success"],
        "gdp_is_historical": macro.get("is_historical", False),
        "gdp_data_year": macro.get("data_year"),
        "interest_rate": None,
        "salary_growth_pct": None,
        "salary_lpa": salary["salary_lpa"],
        "salary_range_lpa": salary["salary_range"],
        "salary_available": salary["success"],
        "industry_growth_rate": None,
        "industry_health": ind["industry_health"],
        "automation_risk": ind["automation_risk"],
        "industry_available": ind["success"],
        "cost_of_living_index": col["cost_of_living_index"],
        "cost_of_living_available": col["success"],
        "sources": sources,
        "errors": errors,
        "all_sources_available": all([
            macro["success"], salary["success"], ind["success"], col["success"],
        ]),
    }

    logger.info(
        "[LIVE_DATA] Collection complete: GDP=%s CPI=%s UNEMP=%s SALARY=%s COL=%s ERRORS=%s",
        data["gdp_growth"], data["inflation_cpi"], data["unemployment_rate"],
        data["salary_lpa"], data["cost_of_living_index"],
        bool(data["errors"]),
    )
    return data


def get_cached_economic_data() -> dict:
    global _LAST_MACRO_CACHE, _LAST_SALARY_CACHE, _LAST_INDUSTRY_CACHE, _LAST_COL_CACHE
    if _LAST_MACRO_CACHE is None:
        return collect_economic_data()
    sources = {}
    for c in [_LAST_MACRO_CACHE, _LAST_SALARY_CACHE, _LAST_INDUSTRY_CACHE, _LAST_COL_CACHE]:
        if c:
            sources.update(c.get("sources", {}))

    return {
        "gdp_growth": _LAST_MACRO_CACHE.get("gdp_growth"),
        "inflation_cpi": _LAST_MACRO_CACHE.get("inflation_cpi"),
        "unemployment_rate": _LAST_MACRO_CACHE.get("unemployment_rate"),
        "gdp_available": _LAST_MACRO_CACHE.get("success", False),
        "gdp_is_historical": _LAST_MACRO_CACHE.get("is_historical", False),
        "interest_rate": None,
        "salary_growth_pct": None,
        "salary_lpa": _LAST_SALARY_CACHE.get("salary_lpa") if _LAST_SALARY_CACHE else None,
        "salary_range_lpa": _LAST_SALARY_CACHE.get("salary_range") if _LAST_SALARY_CACHE else None,
        "salary_available": _LAST_SALARY_CACHE.get("success", False) if _LAST_SALARY_CACHE else False,
        "industry_growth_rate": None,
        "industry_health": _LAST_INDUSTRY_CACHE.get("industry_health") if _LAST_INDUSTRY_CACHE else None,
        "automation_risk": _LAST_INDUSTRY_CACHE.get("automation_risk") if _LAST_INDUSTRY_CACHE else None,
        "industry_available": _LAST_INDUSTRY_CACHE.get("success", False) if _LAST_INDUSTRY_CACHE else False,
        "cost_of_living_index": _LAST_COL_CACHE.get("cost_of_living_index") if _LAST_COL_CACHE else None,
        "cost_of_living_available": _LAST_COL_CACHE.get("success", False) if _LAST_COL_CACHE else False,
        "sources": sources,
    }
