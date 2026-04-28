"""
Regret Agent — thin wrapper around the batch synthesis result.

The actual LLM call (if any) is made by batch_synthesis() in synthesis.py.
This module exists for backward compatibility so api.py can still call
analyze_regret(timeline) per timeline.
"""
from agents.synthesis import get_synthesis_store

_FALLBACK = {
    "lost_opportunity": "Unable to determine — synthesis unavailable.",
    "missed_identity":  "Unable to determine — synthesis unavailable.",
    "emotional_cost":   "Unable to determine — synthesis unavailable.",
}


def analyze_regret(timeline: dict, timeline_key: str = "") -> dict:
    """
    Return regret for a single timeline.
    Reads from the synthesis store populated by batch_synthesis().
    Falls back to a deterministic result if synthesis hasn't run.
    """
    store = get_synthesis_store()
    if store and timeline_key:
        regret = store.get("regrets", {}).get(timeline_key)
        if regret:
            return regret

    # Deterministic fallback: derive from narrative content
    years = [v for k, v in timeline.items() if k.startswith("Year") and isinstance(v, str)]
    last  = years[-1] if years else ""
    return {
        "lost_opportunity": _infer_opportunity(last),
        "missed_identity":  _infer_identity(last),
        "emotional_cost":   _infer_cost(last),
    }


def _infer_opportunity(narrative: str) -> str:
    if "stagnating" in narrative or "constrained" in narrative:
        return "Faster career advancement in a higher-growth environment."
    if "high stress" in narrative or "stress" in narrative:
        return "A less demanding role with better work-life balance."
    return "An alternative path with different risk-reward trade-offs."


def _infer_identity(narrative: str) -> str:
    if "struggling" in narrative:
        return "A version of yourself with greater financial security."
    if "growing steadily" in narrative or "strong" in narrative:
        return "A version who took more risks earlier in their career."
    return "A version who made different trade-offs between income and lifestyle."


def _infer_cost(narrative: str) -> str:
    if "stress" in narrative and "high" in narrative:
        return "The recurring tension between career ambition and personal wellbeing."
    if "managing" in narrative:
        return "The quiet uncertainty of whether a different choice would have been better."
    return "The occasional wonder about roads not taken."
