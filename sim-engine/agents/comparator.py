"""
Comparator Agent — thin wrapper around the batch synthesis result.
"""
from agents.synthesis import get_synthesis_store


def compare_timelines(timelines_with_regrets: dict) -> dict:
    """
    Return cross-timeline comparison.
    Reads from the synthesis store; falls back to deterministic analysis.
    """
    store = get_synthesis_store()
    if store:
        comparison = store.get("comparison")
        if comparison:
            return comparison

    return _deterministic_comparison(timelines_with_regrets)


def _deterministic_comparison(data: dict) -> dict:
    """
    Rule-based comparison — no LLM required.
    Derives patterns from causal score differences across timelines.
    """
    tl_keys = [k for k in data if not k.startswith("_")]

    # Collect Year10 happiness and income scores if available
    happiness_scores = {}
    income_scores    = {}
    for tl_key in tl_keys:
        tl = data[tl_key].get("timeline", data[tl_key])
        # Try to get from _causal if present
        causal = tl.get("_causal", {})
        y10    = causal.get("Year10", {})
        if y10:
            happiness_scores[tl_key] = y10.get("happiness", 50)
            income_scores[tl_key]    = y10.get("income", 50)

    if happiness_scores:
        best_h  = max(happiness_scores, key=happiness_scores.get)
        worst_h = min(happiness_scores, key=happiness_scores.get)
        best_i  = max(income_scores,    key=income_scores.get)
        common  = "All paths involve trade-offs between income growth and personal wellbeing."
        diff    = (
            f"{best_h} leads to the highest happiness by Year 10 "
            f"while {best_i} produces the highest income."
        )
        hinge = (
            "The key determinant is how early career stress is managed — "
            "high early stress compounds negatively on health and relationships over time."
        )
    else:
        common = "All paths share the same starting conditions and economic environment."
        diff   = "The timelines diverge primarily in risk tolerance and career pace."
        hinge  = "The decision itself is the hinge point — each path reflects a different relationship with risk."

    return {
        "common_patterns": common,
        "key_differences": diff,
        "hinge_point":     hinge,
    }
