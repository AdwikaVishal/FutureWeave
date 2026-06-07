from monte_carlo.simulator import run_monte_carlo


def monte_carlo_for_type(decision_type: str, base_scores: dict) -> dict:
    return run_monte_carlo(decision_type, base_scores)
