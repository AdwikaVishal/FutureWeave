from __future__ import annotations
import math
import logging
from typing import Any, Dict, List
from .types import (
    LifeDashboard, AgentOutput, UserProfile, EconomicData,
    FuturePath, DecisionOption, SIMULATION_YEARS,
)

logger = logging.getLogger(__name__)


def compute_life_dashboard(
    future_paths: Dict[str, FuturePath],
    agent_outputs: Dict[str, AgentOutput],
    profile: UserProfile,
    economic: EconomicData,
    options: List[DecisionOption],
) -> LifeDashboard:
    best_path = _find_best_path(future_paths)
    y10 = best_path.years.get("Year10") if best_path else None
    y20 = best_path.years.get("Year20") if best_path else None

    life_satisfaction = _compute_life_satisfaction(best_path, agent_outputs)
    freedom_index = _compute_freedom_index(best_path, profile, economic)
    stress_index = _compute_stress_index(best_path)
    purpose_index = _compute_purpose_index(best_path, agent_outputs)
    wealth_index = _compute_wealth_index(best_path, profile)
    relationship_index = _compute_relationship_index(best_path, profile)
    growth_index = _compute_growth_index(best_path, agent_outputs)
    regret_risk = _compute_overall_regret_risk(agent_outputs)
    decision_confidence = _compute_decision_confidence(agent_outputs)

    scores = [
        life_satisfaction, freedom_index, stress_index, purpose_index,
        wealth_index, relationship_index, growth_index, regret_risk, decision_confidence,
    ]
    overall_score = sum(scores) / len(scores)

    dimensions = {
        "life_satisfaction": round(life_satisfaction, 1),
        "freedom_index": round(freedom_index, 1),
        "stress_index": round(stress_index, 1),
        "purpose_index": round(purpose_index, 1),
        "wealth_index": round(wealth_index, 1),
        "relationship_index": round(relationship_index, 1),
        "growth_index": round(growth_index, 1),
        "regret_risk": round(regret_risk, 1),
        "decision_confidence": round(decision_confidence, 1),
    }

    primary_concern = min(dimensions, key=dimensions.get)
    top_opportunity = max(
        {k: v for k, v in dimensions.items() if k != "regret_risk" and k != "stress_index"},
        key=lambda k: dimensions.get(k, 0),
    )

    trend = _compute_trend(best_path)

    logger.info("[LifeDashboard] overall=%.1f concern=%s opportunity=%s trend=%s",
                overall_score, primary_concern, top_opportunity, trend)

    return LifeDashboard(
        life_satisfaction=round(life_satisfaction, 1),
        freedom_index=round(freedom_index, 1),
        stress_index=round(stress_index, 1),
        purpose_index=round(purpose_index, 1),
        wealth_index=round(wealth_index, 1),
        relationship_index=round(relationship_index, 1),
        growth_index=round(growth_index, 1),
        regret_risk=round(regret_risk, 1),
        decision_confidence=round(decision_confidence, 1),
        dimension_breakdown=dimensions,
        overall_score=round(overall_score, 1),
        trend=trend,
        primary_concern=primary_concern,
        top_opportunity=top_opportunity,
    )


def _find_best_path(future_paths: Dict[str, FuturePath]) -> FuturePath:
    best = None
    best_score = -1
    for p in future_paths.values():
        if p.final_score > best_score:
            best_score = p.final_score
            best = p
    return best


def _compute_life_satisfaction(path: FuturePath, agent_outputs: Dict[str, AgentOutput]) -> float:
    if not path:
        return 50.0
    happy = agent_outputs.get("happiness")
    happy_score = happy.score if happy else 50
    y10 = path.years.get("Year10")
    if y10:
        combined = y10.happiness * 0.5 + happy_score * 0.3 + y10.purpose * 0.2
    else:
        combined = happy_score
    return min(100, combined)


def _compute_freedom_index(path: FuturePath, profile: UserProfile, economic: EconomicData) -> float:
    if not path:
        return 50.0
    y10 = path.years.get("Year10")
    if not y10:
        return 50.0
    financial_freedom = min(y10.net_worth / 100 * 30, 30)
    time_freedom = (100 - y10.stress) * 0.3
    location_freedom = economic.cost_of_living_score / 100.0 * 20
    return min(100, financial_freedom + time_freedom + location_freedom + 20)


def _compute_stress_index(path: FuturePath) -> float:
    if not path:
        return 50.0
    y10 = path.years.get("Year10")
    if not y10:
        return 50.0
    return min(100, y10.stress * 0.6 + y10.burnout_risk * 0.4)


def _compute_purpose_index(path: FuturePath, agent_outputs: Dict[str, AgentOutput]) -> float:
    if not path:
        return 50.0
    identity = agent_outputs.get("identity")
    identity_score = identity.score if identity else 50
    y10 = path.years.get("Year10")
    if y10:
        combined = y10.purpose * 0.5 + identity_score * 0.3 + y10.learning_growth * 0.2
    else:
        combined = identity_score
    return min(100, combined)


def _compute_wealth_index(path: FuturePath, profile: UserProfile) -> float:
    if not path:
        return 50.0
    y10 = path.years.get("Year10")
    if not y10:
        return 50.0
    income_score = y10.income * 0.3
    savings_score = min(y10.savings / 10, 20)
    nw_score = min(y10.net_worth / 100 * 30, 30)
    base = profile.savings / 1000000 * 5
    return min(100, income_score + savings_score + nw_score + base + 10)


def _compute_relationship_index(path: FuturePath, profile: UserProfile) -> float:
    if not path:
        return 50.0
    y10 = path.years.get("Year10")
    if not y10:
        return 50.0
    status_bonus = {"married": 10, "engaged": 8, "in_relationship": 5, "single": 0}.get(profile.relationship_status, 0)
    children_bonus = min(profile.children_count * 5, 10)
    return min(100, y10.relationships * 0.5 + y10.social_support * 0.3 + status_bonus + children_bonus)


def _compute_growth_index(path: FuturePath, agent_outputs: Dict[str, AgentOutput]) -> float:
    if not path:
        return 50.0
    y10 = path.years.get("Year10")
    if not y10:
        return 50.0
    return min(100, y10.learning_growth * 0.4 + y10.career_growth * 0.3 + y10.opportunity * 0.3)


def _compute_overall_regret_risk(agent_outputs: Dict[str, AgentOutput]) -> float:
    regret_agent = agent_outputs.get("regret")
    if regret_agent:
        return 100 - regret_agent.score
    return 50.0


def _compute_decision_confidence(agent_outputs: Dict[str, AgentOutput]) -> float:
    confs = [ao.confidence for ao in agent_outputs.values()]
    if not confs:
        return 50.0
    return min(100, sum(confs) / len(confs) + 10)


def _compute_trend(path: FuturePath) -> str:
    if not path or len(path.years) < 2:
        return "stable"
    y1 = path.years.get("Year1")
    y10 = path.years.get("Year10")
    if y1 and y10:
        delta = (y10.happiness + y10.income + y10.purpose) - (y1.happiness + y1.income + y1.purpose)
        if delta > 20:
            return "strongly_improving"
        elif delta > 5:
            return "improving"
        elif delta > -5:
            return "stable"
        elif delta > -20:
            return "declining"
        else:
            return "strongly_declining"
    return "stable"
