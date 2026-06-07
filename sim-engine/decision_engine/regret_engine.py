from __future__ import annotations
import math
import logging
from typing import Any, Dict, List
from .types import (
    RegretAnalysis, AgentOutput, UserProfile, EconomicData,
    FuturePath, DecisionOption, SIMULATION_YEARS,
)

logger = logging.getLogger(__name__)


def compute_regret(
    decision: str,
    profile: UserProfile,
    economic: EconomicData,
    future_paths: Dict[str, FuturePath],
    agent_outputs: Dict[str, AgentOutput],
    options: List[DecisionOption],
) -> RegretAnalysis:
    age = profile.age
    risk_tol = profile.risk_tolerance

    will_regret_not_trying = _compute_regret_not_trying(age, risk_tol, future_paths, options)
    will_regret_risk = _compute_regret_risk_taken(age, risk_tol, future_paths, options)
    will_regret_delaying = _compute_regret_delaying(age, risk_tol, decision)
    will_regret_comfort = _compute_regret_comfort(age, risk_tol, future_paths, options)

    regrets = [will_regret_not_trying, will_regret_risk, will_regret_delaying, will_regret_comfort]
    overall = sum(regrets) / len(regrets)

    regret_timeline = {}
    for idx, yk in enumerate(SIMULATION_YEARS):
        t = idx + 1
        regret_timeline[yk] = round(min(100, overall * (0.3 + 0.7 * math.log(t + 1, 2) / 5)), 1)

    labels = ["Not trying", "Taking risk", "Delaying", "Staying comfortable"]
    biggest_idx = regrets.index(max(regrets))
    biggest_regret_source = labels[biggest_idx]

    by_option = {}
    for opt in options:
        path = future_paths.get(opt.title)
        if path:
            y10 = path.years.get("Year10", path.years.get("Year5"))
            path_regret = (y10.regret if y10 else 50) * 0.5 + overall * 0.5
            by_option[opt.title] = round(min(100, path_regret), 1)
        else:
            by_option[opt.title] = round(overall, 1)

    regret_letter = _generate_regret_letter(biggest_regret_source, decision, age, overall)

    logger.info("[RegretEngine] overall=%.1f not_try=%.1f risk=%.1f delay=%.1f comfort=%.1f source=%s",
                overall, will_regret_not_trying, will_regret_risk, will_regret_delaying, will_regret_comfort, biggest_regret_source)

    return RegretAnalysis(
        will_regret_not_trying=round(will_regret_not_trying, 1),
        will_regret_risk=round(will_regret_risk, 1),
        will_regret_delaying=round(will_regret_delaying, 1),
        will_regret_comfort=round(will_regret_comfort, 1),
        overall_regret_risk=round(overall, 1),
        regret_timeline=regret_timeline,
        biggest_regret_source=biggest_regret_source,
        regret_letter=regret_letter,
        by_option=by_option,
    )


def _compute_regret_not_trying(age: int, risk_tol: float, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> float:
    base = 50
    age_urgency = min(age / 50 * 25, 25)
    risk_factor = risk_tol * 20
    conservative_paths = sum(1 for o in options if o.risk_level in ("low", "moderate"))
    regret_from_safety = min(conservative_paths * 5, 20)
    return min(100, base + age_urgency + risk_factor + regret_from_safety)


def _compute_regret_risk_taken(age: int, risk_tol: float, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> float:
    base = 40
    income_stability_concern = max(0, 25 - risk_tol * 25)
    age_caution = max(0, (age - 30) * 1.5)
    risky_paths = sum(1 for o in options if o.risk_level == "high")
    regret_from_risk = min(risky_paths * 8, 25)
    return min(100, base + income_stability_concern + age_caution + regret_from_risk)


def _compute_regret_delaying(age: int, risk_tol: float, decision: str) -> float:
    base = 45
    age_factor = min(age / 40 * 20, 20)
    risk_factor = risk_tol * 15
    time_sensitive = 10 if any(w in decision.lower() for w in ["now", "soon", "year", "gap", "delay", "wait"]) else 0
    return min(100, base + age_factor + risk_factor + time_sensitive)


def _compute_regret_comfort(age: int, risk_tol: float, future_paths: Dict[str, FuturePath], options: List[DecisionOption]) -> float:
    base = 35
    age_midlife = max(0, (age - 35) * 2)
    ambition_factor = (1 - risk_tol) * 20
    comfortable_paths = sum(1 for o in options if o.risk_level == "low")
    regret_from_comfort = min(comfortable_paths * 7, 20)
    return min(100, base + age_midlife + ambition_factor + regret_from_comfort)


def _generate_regret_letter(source: str, decision: str, age: int, regret_score: float) -> str:
    templates = {
        "Not trying": (
            f"Future you at {age + 20} looking back on '{decision}' — "
            f"the question that haunts you most is 'what if?' "
            f"You had the courage to imagine a different path, but fear kept you anchored. "
            f"The regret of not trying grows heavier with each passing year. "
            f"You didn't fail — you simply never gave yourself the chance."
        ),
        "Taking risk": (
            f"Future you at {age + 20} reflecting on '{decision}' — "
            f"the risks you took were real, and some didn't pay off. "
            f"You wonder if a more measured approach would have brought the same rewards "
            f"with fewer sleepless nights. "
            f"The regret isn't the risk itself — it's not knowing if you over-gambled."
        ),
        "Delaying": (
            f"Future you at {age + 20} thinking about '{decision}' — "
            f"you waited for the perfect moment that never came. "
            f"The window of opportunity closed while you were still weighing options. "
            f"Time, unlike other resources, cannot be earned back. "
            f"The deepest regret is knowing you had your chance and let it slip away."
        ),
        "Staying comfortable": (
            f"Future you at {age + 20} remembering '{decision}' — "
            f"you chose the comfortable path, and it was… fine. "
            f"Not terrible, not extraordinary — just fine. "
            f"But 'fine' has a way of turning into 'is this all there is?' "
            f"The regret of staying comfortable isn't dramatic — it's the slow ache of unrealized potential."
        ),
    }
    letter = templates.get(source, templates["Not trying"])
    if regret_score > 65:
        letter += f" Your regret risk ({regret_score:.0f}%) is significant. Take this decision seriously."
    elif regret_score < 35:
        letter += f" Your regret risk ({regret_score:.0f}%) is low. You're approaching this wisely."
    return letter
