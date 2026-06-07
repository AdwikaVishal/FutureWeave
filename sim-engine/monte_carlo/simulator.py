"""Monte Carlo simulation with stochastic outcomes per decision type."""
from typing import Any
import random
import statistics


def run_monte_carlo(
    decision_type: str,
    base_scores: dict[str, float],
    iterations: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    random.seed(seed)

    if decision_type == "educational":
        variables = ["admission_probability", "seat_availability", "placement_probability", "burnout_risk", "future_optionality"]
        # Educational outcomes are moderately stochastic
        stochastic_params = {"admission_probability": 0.12, "seat_availability": 0.15, "placement_probability": 0.10, "burnout_risk": 0.18, "future_optionality": 0.10}
    elif decision_type == "career":
        variables = ["income", "career_growth", "job_security", "stress", "opportunity"]
        # Career has higher income uncertainty
        stochastic_params = {"income": 0.15, "career_growth": 0.12, "job_security": 0.10, "stress": 0.10, "opportunity": 0.12}
    elif decision_type == "financial":
        variables = ["market_return", "inflation_impact", "liquidity", "risk", "tax_efficiency"]
        stochastic_params = {"market_return": 0.20, "inflation_impact": 0.10, "liquidity": 0.08, "risk": 0.12, "tax_efficiency": 0.05}
    elif decision_type == "relocation":
        variables = ["visa_success", "employment_success", "integration_score", "quality_of_life", "safety"]
        stochastic_params = {"visa_success": 0.20, "employment_success": 0.15, "integration_score": 0.12, "quality_of_life": 0.08, "safety": 0.06}
    elif decision_type == "business":
        variables = ["revenue_growth", "competition", "funding_success", "profitability", "market_fit"]
        stochastic_params = {"revenue_growth": 0.25, "competition": 0.10, "funding_success": 0.22, "profitability": 0.18, "market_fit": 0.12}
    elif decision_type == "health":
        variables = ["treatment_success", "recovery_rate", "quality_of_life", "side_effect_risk", "long_term_outlook"]
        stochastic_params = {"treatment_success": 0.12, "recovery_rate": 0.14, "quality_of_life": 0.08, "side_effect_risk": 0.10, "long_term_outlook": 0.10}
    else:
        variables = list(base_scores.keys())
        stochastic_params = {v: 0.15 for v in variables}

    base = {k: v for k, v in base_scores.items() if k in variables}
    if not base:
        base = {v: 50 for v in variables}

    # Per-variable noise width uses stochastic_params
    results: dict[str, list[float]] = {v: [] for v in variables}
    for _ in range(iterations):
        for var in variables:
            b = base.get(var, 50)
            sigma = 8 * stochastic_params.get(var, 0.15) / 0.15  # scale from base 8
            noise = random.gauss(0, max(1.0, sigma))
            val = max(0, min(100, b + noise))
            results[var].append(val)

    output = {}
    for var in variables:
        vals = sorted(results[var])
        output[var] = {
            "mean": round(statistics.mean(vals), 1),
            "median": round(statistics.median(vals), 1),
            "std": round(statistics.stdev(vals), 1),
            "p10": round(vals[int(iterations * 0.1)], 1),
            "p50": round(vals[int(iterations * 0.5)], 1),
            "p90": round(vals[int(iterations * 0.9)], 1),
        }

    # Success/failure classification
    success_threshold = 60
    failure_threshold = 35
    overall_scores = []
    for i in range(iterations):
        avg = sum(results[v][i] for v in variables) / len(variables)
        overall_scores.append(avg)
    successes = sum(1 for s in overall_scores if s >= success_threshold)
    failures = sum(1 for s in overall_scores if s <= failure_threshold)
    neutrals = iterations - successes - failures

    return {
        "decision_type": decision_type,
        "iterations": iterations,
        "variables": variables,
        "results": output,
        "overall_score": round(statistics.mean(
            output[v]["mean"] for v in variables
        ), 1),
        "success_probability": round(successes / iterations, 2),
        "failure_probability": round(failures / iterations, 2),
        "neutral_probability": round(neutrals / iterations, 2),
    }
