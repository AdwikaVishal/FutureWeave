from __future__ import annotations
import math
import random
import logging
from typing import Any, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from .types import MonteCarloResult, UserProfile, EconomicData, SIMULATION_YEARS

logger = logging.getLogger(__name__)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _logistic(base: float, cap: float, rate: float, t: float) -> float:
    return base + (cap - base) * (1 - math.exp(-rate * t))


def _run_single(
    profile: UserProfile,
    base_economic: EconomicData,
    iteration: int,
) -> Dict[str, Dict[str, Dict[str, float]]]:
    random.seed(iteration * 1337 + 42)

    salary_score = base_economic.salary_score / 100.0
    economic_score = base_economic.economic_score / 100.0
    employment_score = base_economic.employment_score / 100.0
    industry_score = base_economic.industry_score / 100.0
    col_score = base_economic.cost_of_living_score / 100.0

    gdp_volatility = max(0.5, 1.5 * (1.5 - economic_score))
    infl_volatility = max(0.5, 1.0 * (1.5 - economic_score))
    ind_volatility = max(1.0, 5.0 * (1.3 - industry_score))
    sal_volatility = max(0.5, 2.0 * (1.3 - salary_score))
    unemp_volatility = max(0.5, 1.0 * (1.5 - employment_score))

    gdp = base_economic.gdp_growth + random.gauss(0, gdp_volatility)
    infl = base_economic.inflation_cpi + random.gauss(0, infl_volatility)
    ind_health = base_economic.industry_health + random.gauss(0, ind_volatility)
    sal_growth = base_economic.salary_growth_pct + random.gauss(0, sal_volatility)
    risk_val = base_economic.automation_risk + random.gauss(0, 3.0)

    econ = EconomicData(
        gdp_growth=_clamp(gdp, -5, 15),
        inflation_cpi=_clamp(infl, 0, 15),
        industry_health=_clamp(ind_health, 20, 100),
        salary_growth_pct=_clamp(sal_growth, 0, 20),
        automation_risk=_clamp(risk_val, 0, 50),
        unemployment_rate=base_economic.unemployment_rate + random.gauss(0, unemp_volatility),
        cost_of_living_index=_clamp(base_economic.cost_of_living_index + random.gauss(0, 0.1 * (2 - col_score)), 0.5, 3.0),
        interest_rate=_clamp(base_economic.interest_rate + random.gauss(0, 1.0), 0, 15),
        salary_score=base_economic.salary_score,
        economic_score=base_economic.economic_score,
        employment_score=base_economic.employment_score,
        industry_score=base_economic.industry_score,
        cost_of_living_score=base_economic.cost_of_living_score,
    )

    paths = [
        ("The Settler", {"income": 0.0, "career": 0.05, "calm": 0.2, "health": 0.1, "social": 0.1, "happiness": 0.05, "opportunity": -0.1, "freedom": -0.1, "purpose": -0.05}),
        ("The Climber", {"income": 0.05, "career": 0.1, "calm": 0.0, "health": 0.05, "social": 0.0, "happiness": 0.05, "opportunity": 0.05, "freedom": 0.0, "purpose": 0.05}),
        ("The Gambler", {"income": 0.1, "career": 0.2, "calm": -0.2, "health": -0.1, "social": -0.1, "happiness": 0.0, "opportunity": 0.2, "freedom": 0.1, "purpose": 0.1}),
    ]

    result = {}
    for key, bias in paths:
        year_scores = {}
        for idx, yk in enumerate(SIMULATION_YEARS):
            t = idx + 1
            risk_t = profile.risk_tolerance + random.gauss(0, 0.05)

            effective_sal_growth = econ.salary_growth_pct / 100.0 * (0.5 + 0.3 * salary_score + 0.2 * industry_score)
            effective_ind_health = econ.industry_health / 100.0 * (0.6 + 0.2 * industry_score + 0.2 * economic_score)
            effective_gdp = econ.gdp_growth / 100.0 * (0.7 + 0.3 * economic_score)
            employment_modifier = 0.8 + 0.4 * employment_score
            col_pressure = max(0, (econ.cost_of_living_index - 1.0) * 0.1)
            pb = bias

            income = _clamp(_logistic(25, 95 * effective_ind_health, 0.3 * (1 + effective_sal_growth) * (1 + pb.get("income", 0)) * employment_modifier, t) + random.gauss(0, 3))
            career = _clamp(_logistic(20, 90, 0.25 * effective_ind_health * (1 + pb.get("career", 0)) * employment_modifier, t) * (0.7 + 0.3 * salary_score) + random.gauss(0, 3))
            stress = _clamp(40 + 30 * (1 - math.exp(-0.2 * t)) - 15 * pb.get("calm", 0) + 10 * risk_t + col_pressure * 20 + max(0, infl / 100.0 - 0.05) * 50 + random.gauss(0, 5))
            health = _clamp(70 - 10 * (1 - math.exp(-0.15 * t)) - 5 * stress / 100 + 8 * pb.get("health", 0) - col_pressure * 10 + random.gauss(0, 3))
            rel = _clamp(60 - 8 * (1 - math.exp(-0.2 * t)) + 12 * pb.get("social", 0) - 3 * risk_t * 10 - col_pressure * 5 + random.gauss(0, 5))
            purpose = _clamp(30 + career * 0.25 + (100 - stress) * 0.15 + rel * 0.15 + 10 * pb.get("purpose", 0) + economic_score * 8 + random.gauss(0, 4))
            freedom = _clamp(50 + income * 0.2 - stress * 0.3 + career * 0.1 + 15 * pb.get("freedom", 0) + economic_score * 10 + random.gauss(0, 4))
            opp = _clamp(30 + career * 0.35 + risk_t * 15 + effective_ind_health * 10 + 10 * pb.get("opportunity", 0) + economic_score * 10 + employment_score * 5 + random.gauss(0, 5))
            happ = _clamp(50 + 0.12 * (income - 50) + 0.15 * (health - 50) + 0.2 * (rel - 50) + 0.12 * (career - 50) + 0.1 * (purpose - 50) - 0.1 * stress + 5 * pb.get("happiness", 0) + effective_gdp * 5 - col_pressure * 5 + random.gauss(0, 4))
            regret_val = _clamp(20 + (100 - happ) * 0.3 + (100 - purpose) * 0.2 + stress * 0.2 + random.gauss(0, 5))

            year_scores[yk] = {
                "income": income, "career_growth": career, "stress": stress,
                "health": health, "relationships": rel, "happiness": happ,
                "opportunity": opp, "purpose": purpose, "freedom": freedom,
                "regret": regret_val,
            }
        result[key] = year_scores
    return result


def run_monte_carlo(
    profile: UserProfile,
    economic: EconomicData,
    iterations: int = 10000,
    workers: int = 8,
) -> MonteCarloResult:
    all_results = []
    batch_size = max(100, iterations // workers)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = []
        for i in range(0, iterations, batch_size):
            n = min(batch_size, iterations - i)
            for j in range(n):
                futures.append(ex.submit(_run_single, profile, economic, i + j))
        for f in as_completed(futures):
            all_results.append(f.result())

    NODES = ["income", "career_growth", "stress", "health", "relationships", "happiness", "opportunity", "purpose", "freedom", "regret"]
    PATHS = ["The Settler", "The Climber", "The Gambler"]

    node_values: Dict[str, List[float]] = {n: [] for n in NODES}
    path_final: Dict[str, List[float]] = {k: [] for k in PATHS}
    regret_values: List[float] = []

    for run in all_results:
        for path_key in PATHS:
            year_scores_list = [run[path_key][yk] for yk in SIMULATION_YEARS]
            final_hap = sum(ys["happiness"] for ys in year_scores_list) / len(year_scores_list)
            path_final[path_key].append(final_hap)
            for n in NODES:
                avg = sum(ys[n] for ys in year_scores_list) / len(year_scores_list)
                node_values[n].append(avg)
        regret_values.extend(ys["regret"] for ys in run[PATHS[0]].values())

    distributions = {}
    percentiles = {}
    for n in NODES:
        vals = sorted(node_values[n])
        n_vals = len(vals)
        mu = sum(vals) / n_vals if n_vals else 0
        var = sum((v - mu) ** 2 for v in vals) / n_vals if n_vals else 0
        distributions[n] = {
            "mean": round(mu, 1), "median": round(vals[n_vals // 2] if n_vals else 0, 1),
            "std": round(math.sqrt(var), 1), "variance": round(var, 1),
            "min": round(vals[0], 1) if n_vals else 0, "max": round(vals[-1], 1) if n_vals else 0,
        }
        percentiles[n] = {
            "p5": round(vals[int(n_vals * 0.05)] if n_vals else 0, 1),
            "p25": round(vals[int(n_vals * 0.25)] if n_vals else 0, 1),
            "p50": round(vals[n_vals // 2] if n_vals else 0, 1),
            "p75": round(vals[int(n_vals * 0.75)] if n_vals else 0, 1),
            "p95": round(vals[int(n_vals * 0.95)] if n_vals else 0, 1),
        }

    path_comparison = {}
    for k in PATHS:
        vals = sorted(path_final[k])
        n = len(vals)
        path_comparison[k] = {
            "mean": round(sum(vals) / n, 1) if n else 0,
            "median": round(vals[n // 2], 1) if n else 0,
            "std": round(math.sqrt(sum((v - sum(vals)/n) ** 2 for v in vals) / n), 1) if n else 0,
        }

    climber_vals = sorted(path_final["The Climber"])
    success = sum(1 for v in climber_vals if v >= 60)
    failure = sum(1 for v in climber_vals if v < 40)
    total = len(climber_vals) or 1

    regret_sorted = sorted(regret_values)
    regret_prob = sum(1 for r in regret_values if r > 50) / max(len(regret_values), 1) * 100

    happiness_vals = sorted(node_values["happiness"])
    best_case = {
        "income": round(sum(sorted(node_values["income"])[-int(len(node_values["income"]) * 0.1):]) / max(int(len(node_values["income"]) * 0.1), 1), 1),
        "career_growth": round(sum(sorted(node_values["career_growth"])[-int(len(node_values["career_growth"]) * 0.1):]) / max(int(len(node_values["career_growth"]) * 0.1), 1), 1),
        "happiness": round(happiness_vals[-1] if happiness_vals else 0, 1),
        "net_worth": round(sum(sorted(node_values.get("income", [50]))[-int(len(node_values.get("income", [50])) * 0.1):]) / max(int(len(node_values.get("income", [50])) * 0.1), 1) * 10, 1),
        "purpose": round(sum(sorted(node_values["purpose"])[-int(len(node_values["purpose"]) * 0.1):]) / max(int(len(node_values["purpose"]) * 0.1), 1), 1),
        "freedom": round(sum(sorted(node_values["freedom"])[-int(len(node_values["freedom"]) * 0.1):]) / max(int(len(node_values["freedom"]) * 0.1), 1), 1),
    }
    expected_case = {
        "income": round(distributions.get("income", {}).get("mean", 50), 1),
        "career_growth": round(distributions.get("career_growth", {}).get("mean", 50), 1),
        "happiness": round(distributions.get("happiness", {}).get("mean", 50), 1),
        "net_worth": round(distributions.get("income", {}).get("mean", 50) * 10, 1),
        "purpose": round(distributions.get("purpose", {}).get("mean", 50), 1),
        "freedom": round(distributions.get("freedom", {}).get("mean", 50), 1),
    }
    worst_case = {
        "income": round(sum(sorted(node_values["income"])[:max(int(len(node_values["income"]) * 0.1), 1)]) / max(int(len(node_values["income"]) * 0.1), 1), 1),
        "career_growth": round(sum(sorted(node_values["career_growth"])[:max(int(len(node_values["career_growth"]) * 0.1), 1)]) / max(int(len(node_values["career_growth"]) * 0.1), 1), 1),
        "happiness": round(happiness_vals[0] if happiness_vals else 0, 1),
        "net_worth": round(sum(sorted(node_values.get("income", [50]))[:max(int(len(node_values.get("income", [50])) * 0.1), 1)]) / max(int(len(node_values.get("income", [50])) * 0.1), 1) * 10, 1),
        "purpose": round(happiness_vals[0] if happiness_vals else 0, 1) if len(node_values.get("purpose", [])) < 100 else round(sum(sorted(node_values["purpose"])[:max(int(len(node_values["purpose"]) * 0.1), 1)]) / max(int(len(node_values["purpose"]) * 0.1), 1), 1),
        "freedom": round(happiness_vals[0] if happiness_vals else 0, 1) if len(node_values.get("freedom", [])) < 100 else round(sum(sorted(node_values["freedom"])[:max(int(len(node_values["freedom"]) * 0.1), 1)]) / max(int(len(node_values["freedom"]) * 0.1), 1), 1),
    }

    risk_metrics = {
        "value_at_risk_95": round(percentiles.get("happiness", {}).get("p5", 0) - distributions.get("happiness", {}).get("mean", 50), 1),
        "expected_shortfall": round(percentiles.get("happiness", {}).get("p5", 0), 1),
        "coefficient_of_variation": round(math.sqrt(distributions.get("happiness", {}).get("variance", 0)) / max(distributions.get("happiness", {}).get("mean", 1), 0.01), 2),
        "regret_at_risk": round(percentiles.get("regret", {}).get("p95", 50), 1),
        "downside_deviation": round(math.sqrt(sum((v - 50) ** 2 for v in node_values.get("happiness", [50]) if v < 50) / max(len([v for v in node_values.get("happiness", [50]) if v < 50]), 1)), 1),
    }

    logger.info("[MonteCarlo] %d iterations completed", iterations)
    logger.info("[MonteCarlo] Success=%.1f%% Failure=%.1f%% Regret risk=%.1f%%",
                success / total * 100, failure / total * 100, regret_prob)

    return MonteCarloResult(
        iterations=iterations,
        node_distributions=distributions,
        percentiles=percentiles,
        success_probability=round(success / total * 100, 1),
        failure_probability=round(failure / total * 100, 1),
        risk_metrics=risk_metrics,
        timeline_comparison=path_comparison,
        best_case=best_case,
        expected_case=expected_case,
        worst_case=worst_case,
        regret_probability=round(regret_prob, 1),
        opportunity_cost=round(100 - expected_case.get("happiness", 50), 1),
        path_dependencies={k: v["mean"] for k, v in path_comparison.items()},
    )
