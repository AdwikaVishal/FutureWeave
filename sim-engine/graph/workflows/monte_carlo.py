import json
import logging
import math
import random
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from deterministic_formulas import (
    compute_skill_growth, compute_net_worth,
    compute_financial_risk, compute_stress,
    compute_burnout_risk, compute_work_life_balance,
    compute_physical_health, compute_mental_health,
    compute_family_stability, compute_social_connection,
    compute_relationship_wealth, compute_year_scores,
)
from services.sync_data import collect_economic_data, get_data_sources

logger = logging.getLogger(__name__)

TIMELINE_ARCHETYPES = ["Timeline A", "Timeline B", "Timeline C"]
YEARS = ["Year1", "Year3", "Year5", "Year7", "Year10"]
NODES = ["income", "career_growth", "stress", "health", "relationships", "happiness", "opportunity"]


def run_monte_carlo(
    decision: str,
    context: dict,
    iterations: int = 10000,
    parallel: bool = True,
) -> dict:
    logger.info("[MonteCarlo] Running %d iterations for: %s", iterations, decision[:60])

    live_data = collect_economic_data(decision, context)

    if not live_data.get("all_sources_available"):
        logger.warning(
            "[MonteCarlo] Live data incomplete: %d sources available. Using stochastic simulation with partial data.",
            sum(1 for k in ["gdp_available", "salary_available"] if live_data.get(k)),
        )

    if parallel and iterations >= 100:
        results = _run_parallel(decision, context, live_data, iterations)
    else:
        results = _run_sequential(decision, context, live_data, iterations)

    analysis = _analyze_results(results, iterations)
    analysis["data_sources"] = _build_source_attribution(live_data)
    analysis["live_data"] = {
        k: v for k, v in live_data.items()
        if k not in ("sources", "errors")
        and v is not None
    }
    available_count = sum(1 for k in ["gdp_available", "salary_available", "industry_available", "cost_of_living_available"] if live_data.get(k))
    analysis["data_quality"] = {
        "all_sources_available": live_data.get("all_sources_available", False),
        "available_sources": available_count,
        "total_sources": 4,
        "fallback_mode": available_count == 0,
        "errors": live_data.get("errors", {}),
    }
    logger.info("[MonteCarlo] Complete: success=%.1f%% failure=%.1f%% sources=%d errors=%d",
                analysis["success_probability"] * 100,
                analysis["failure_probability"] * 100,
                len(analysis.get("data_sources", {})),
                len(live_data.get("errors", {})))
    return analysis


def _run_single_iteration(decision: str, context: dict, live_data: dict, seed: int) -> dict:
    random.seed(seed)
    profile = {}

    gdp = live_data.get("gdp_growth")
    cpi = live_data.get("inflation_cpi")
    interest = live_data.get("interest_rate")
    salary_growth = live_data.get("salary_growth_pct")
    ind_health = live_data.get("industry_health")
    automation = live_data.get("automation_risk")
    unemp = live_data.get("unemployment_rate")
    salary_lpa = live_data.get("salary_lpa")

    has_gdp = gdp is not None
    has_cpi = cpi is not None
    has_salary = salary_lpa is not None

    if has_salary and salary_lpa:
        base_salary = salary_lpa
    elif has_gdp and gdp:
        base_salary = max(3.0, gdp * 1.5)
    else:
        base_salary = None

    economic = {
        "gdp_growth": max(2.0, random.gauss(gdp or 5.0, 1.5)) if has_gdp else random.gauss(5.0, 1.5),
        "inflation_cpi": max(1.0, random.gauss(cpi or 4.0, 1.0)) if has_cpi else random.gauss(4.0, 1.0),
        "interest_rate": max(2.0, random.gauss(interest or 5.0, 1.0)),
        "salary_growth_pct": max(2.0, random.gauss(salary_growth or 5.0, 2.0)),
        "industry_growth_rate": max(0.0, random.gauss(8.0, 2.5)),
        "automation_risk": max(0, min(80, random.gauss(automation or 20, 8))),
        "unemployment_rate": max(1.0, random.gauss(unemp or 5.0, 1.0)),
        "industry_health": max(30, min(100, random.gauss(ind_health or 60, 10))),
    }

    anchors = {
        "salary_lpa": max(2, random.gauss(base_salary or 8.0, 2.0)),
        "work_hours": max(30, min(80, context.get("work_hours", 45) + random.gauss(0, 8))),
        "savings_rate": max(5, min(80, random.gauss(44.3, 12))),
        "disposable_income": max(10000, random.gauss(35000, 10000)),
        "stress_baseline": max(10, min(100, random.gauss(55, 15))),
    }

    result = {
        "seed": seed,
        "economic": {k: round(v, 2) for k, v in economic.items()},
        "scores": {},
        "timeline_details": {},
        "live_data_used": {
            "gdp_available": has_gdp,
            "cpi_available": has_cpi,
            "salary_available": has_salary,
        },
    }

    personality_map = {"Timeline A": "A", "Timeline B": "B", "Timeline C": "C"}

    for tl_key in TIMELINE_ARCHETYPES:
        pkey = personality_map[tl_key]
        tl_scores = {}
        for y in YEARS:
            scores = compute_year_scores(profile, context, economic, anchors, y, pkey)
            tl_scores[y] = scores

        result["scores"][tl_key] = {}
        for node in NODES:
            values = [v[node] for v in tl_scores.values()]
            result["scores"][tl_key][node] = round(statistics.mean(values), 1)

        result["timeline_details"][tl_key] = tl_scores

    income_values = [result["scores"][tl]["income"] for tl in TIMELINE_ARCHETYPES]
    stress_values = [result["scores"][tl]["stress"] for tl in TIMELINE_ARCHETYPES]
    result["max_income"] = max(income_values)
    result["avg_income"] = statistics.mean(income_values)
    result["avg_stress"] = statistics.mean(stress_values)
    return result


def _run_sequential(decision: str, context: dict, live_data: dict, iterations: int) -> List[dict]:
    return [_run_single_iteration(decision, context, live_data, i) for i in range(iterations)]


def _run_parallel(decision: str, context: dict, live_data: dict, iterations: int) -> List[dict]:
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_run_single_iteration, decision, context, live_data, i): i for i in range(iterations)}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                logger.error("[MonteCarlo] Iteration %d failed: %s", futures[future], exc)
    return results


def _analyze_results(results: List[dict], iterations: int) -> dict:
    if not results:
        return {
            "success_probability": 0.0,
            "failure_probability": 0.0,
            "neutral_probability": 1.0,
            "regret_probability": 0.0,
            "iterations_run": 0,
            "iterations_requested": iterations,
        }

    income_values = [r["max_income"] for r in results if r.get("max_income") is not None]
    happiness_values = []
    stress_values = []
    for r in results:
        for tl_key in TIMELINE_ARCHETYPES:
            s = r.get("scores", {}).get(tl_key, {})
            if s.get("happiness") is not None:
                happiness_values.append(s["happiness"])
            if s.get("stress") is not None:
                stress_values.append(s["stress"])

    if income_values:
        sorted_income = sorted(income_values)
        n = len(sorted_income)
        p75 = sorted_income[min(n - 1, int(n * 0.75))]
        p25 = sorted_income[max(0, int(n * 0.25))]

        success_count = sum(1 for v in income_values if v >= p75)
        failure_count = sum(1 for v in income_values if v <= p25)
        neutral_count = len(results) - success_count - failure_count

        if happiness_values and income_values:
            sorted_happiness = sorted(happiness_values)
            p25_happy = sorted_happiness[max(0, len(sorted_happiness) // 4)]
            p50_income = sorted_income[max(0, n // 2)]

            regret_count = sum(
                1 for i, r in enumerate(results)
                if r["max_income"] >= p50_income
                and any(
                    r.get("scores", {}).get(tl, {}).get("happiness", 100) <= p25_happy
                    for tl in TIMELINE_ARCHETYPES
                )
            )
        else:
            regret_count = 0
    else:
        success_count = 0
        failure_count = 0
        neutral_count = iterations
        regret_count = 0

    sorted_incomes = sorted(income_values) if income_values else [50]
    sorted_happiness = sorted(happiness_values) if happiness_values else [50]
    sorted_stress = sorted(stress_values) if stress_values else [50]

    def confidence_interval(data: List[float]) -> dict:
        if len(data) < 2:
            return {"lower": 0, "upper": 100, "median": 50}
        n = len(data)
        return {
            "lower": round(data[max(0, n // 40)], 1),
            "upper": round(data[min(n - 1, n - n // 40 - 1)], 1),
            "median": round(statistics.median(data), 1),
            "mean": round(statistics.mean(data), 1),
            "std_dev": round(statistics.stdev(data), 1) if len(data) > 1 else 0,
        }

    return {
        "success_probability": round(success_count / len(results), 4),
        "failure_probability": round(failure_count / len(results), 4),
        "neutral_probability": round(neutral_count / len(results), 4),
        "regret_probability": round(regret_count / len(results), 4),
        "iterations_run": len(results),
        "iterations_requested": iterations,
        "income_distribution": {
            "min": round(min(income_values), 1) if income_values else 0,
            "max": round(max(income_values), 1) if income_values else 0,
            **confidence_interval(income_values),
        },
        "happiness_distribution": confidence_interval(sorted_happiness) if happiness_values else {"lower": 0, "upper": 100, "median": 50},
        "stress_distribution": confidence_interval(sorted_stress) if stress_values else {"lower": 0, "upper": 100, "median": 50},
        "timeline_comparison": _timeline_comparison(results),
    }


def _timeline_comparison(results: List[dict]) -> dict:
    comparison = {}
    for tl_key in TIMELINE_ARCHETYPES:
        tl_scores = {node: [] for node in NODES}
        for r in results:
            scores = r.get("scores", {}).get(tl_key, {})
            for node in NODES:
                if node in scores:
                    tl_scores[node].append(scores[node])

        comparison[tl_key] = {
            node: {
                "mean": round(statistics.mean(vals), 1) if vals else 0,
                "std": round(statistics.stdev(vals), 1) if len(vals) > 1 else 0,
            }
            for node, vals in tl_scores.items() if vals
        }
    return comparison


def _build_source_attribution(live_data: dict) -> dict:
    sources = live_data.get("sources", {})
    attribution = {}

    metric_map = {
        "worldbank": ["gdp_growth", "inflation_cpi", "unemployment_rate"],
        "ambitionbox": ["salary_lpa", "salary_range_lpa"],
        "fred": ["industry_health", "automation_risk"],
        "numbeo": ["cost_of_living_index"],
    }

    errors = live_data.get("errors", {})

    for provider_key, metrics in metric_map.items():
        info = sources.get(provider_key, {})
        provider_error = errors.get(provider_key)
        if info and info.get("available"):
            attribution[provider_key] = {
                "available": True,
                "url": info.get("url", ""),
                "metrics": [m for m in metrics if m in live_data and live_data[m] is not None],
            }
        else:
            attribution[provider_key] = {
                "available": False,
                "url": info.get("url", "") if info else "",
                "metrics": [m for m in metrics if m in live_data and live_data[m] is not None],
                "error": provider_error or "unavailable",
            }

    total = sum(1 for v in attribution.values() if v.get("available"))
    total_possible = len(attribution)
    attribution["_summary"] = {
        "live_sources": total,
        "total_sources": total_possible,
        "data_quality_pct": round(total / max(total_possible, 1) * 100, 0),
        "data_available": total > 0,
    }
    return attribution
