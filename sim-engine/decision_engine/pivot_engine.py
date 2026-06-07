from __future__ import annotations
from typing import Any, Dict, Optional
from .types import (
    PivotResult, FuturePath, YearScores, UserProfile, EconomicData,
    AgentOutput, DebateResult, SIMULATION_YEARS,
)
from .timeline_engine import compute_year_scores, _option_bias


def compute_pivot(
    profile: UserProfile,
    economic: EconomicData,
    original_timeline: FuturePath,
    event_year: str,
    alternative_outcome: str,
    agent_outputs: Optional[Dict[str, AgentOutput]] = None,
) -> PivotResult:
    bias = _option_bias(original_timeline.label)
    modification = _parse_modification(alternative_outcome, bias)
    modified_bias = {**bias, **modification}

    pivoted_years = {}
    for yk in SIMULATION_YEARS:
        pivoted_years[yk] = compute_year_scores(profile, economic, yk, modified_bias)

    pivoted_events = list(original_timeline.events)
    pivoted_events.append({
        "year": event_year,
        "type": "pivot",
        "name": alternative_outcome[:60],
        "impact": "modified",
        "description": alternative_outcome,
    })

    scores = [pivoted_years[yk].happiness for yk in SIMULATION_YEARS if yk in pivoted_years]
    pivoted = FuturePath(
        option_key=original_timeline.option_key + " (Pivoted)",
        label=original_timeline.label + " (Pivoted)",
        archetype=original_timeline.archetype,
        years=pivoted_years,
        events=pivoted_events,
        final_score=round(sum(scores) / len(scores), 1) if scores else 50,
    )

    deltas = {}
    for n in ["income", "career_growth", "health", "relationships", "happiness", "opportunity", "stress"]:
        orig_final = getattr(original_timeline.years.get("Year10", YearScores()), n, 50)
        piv_final = getattr(pivoted.years.get("Year10", YearScores()), n, 50)
        deltas[n] = round(piv_final - orig_final, 1)

    agent_changes = {}
    if agent_outputs:
        for name in agent_outputs:
            delta = 0
            if name in alternative_outcome.lower():
                delta = 5
            elif "risk" in name.lower():
                delta = -3 if "startup" in alternative_outcome.lower() else 2
            elif "career" in name.lower():
                delta = 8 if "startup" in alternative_outcome.lower() else -3
            agent_changes[name] = delta

    return PivotResult(
        original_timeline=original_timeline,
        pivoted_timeline=pivoted,
        deltas=deltas,
        agent_changes=agent_changes,
        confidence_change=round(sum(abs(v) for v in deltas.values()) / len(deltas) * -0.5, 1),
    )


def _parse_modification(text: str, base_bias: Dict[str, float]) -> Dict[str, float]:
    text_lower = text.lower()
    mods = {}
    if any(w in text_lower for w in ["startup", "found", "launch", "entrepreneur"]):
        mods["income"] = 0.3
        mods["calm"] = -0.25
        mods["opportunity"] = 0.3
        mods["health"] = -0.1
    elif any(w in text_lower for w in ["stable", "corporate", "mnc", "government"]):
        mods["income"] = -0.05
        mods["calm"] = 0.2
        mods["health"] = 0.1
        mods["social"] = 0.1
        mods["opportunity"] = -0.1
    elif any(w in text_lower for w in ["relocate", "move", "abroad", "country"]):
        mods["income"] = 0.15
        mods["calm"] = -0.15
        mods["opportunity"] = 0.2
        mods["social"] = -0.15
    elif any(w in text_lower for w in ["study", "degree", "master", "mba", "education"]):
        mods["career"] = 0.2
        mods["income"] = -0.1
        mods["calm"] = -0.1
        mods["opportunity"] = 0.2
    elif any(w in text_lower for w in ["health", "family", "balance", "slow"]):
        mods["health"] = 0.2
        mods["calm"] = 0.25
        mods["social"] = 0.15
        mods["career"] = -0.15
        mods["income"] = -0.1
    return mods
