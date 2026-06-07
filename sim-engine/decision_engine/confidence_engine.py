from __future__ import annotations
import math
import logging
from typing import Any, Dict, List
from .types import ConfidenceBreakdown, AgentOutput, MonteCarloResult, EconomicData

NODES = ["income", "career_growth", "stress", "health", "relationships", "happiness", "opportunity"]

logger = logging.getLogger(__name__)


def compute_confidence(
    agent_outputs: Dict[str, AgentOutput],
    monte_carlo: MonteCarloResult,
    economic: EconomicData,
    missing_data_fields: List[str],
) -> ConfidenceBreakdown:
    agent_agreement = _compute_agent_agreement(agent_outputs)
    data_quality = _compute_data_quality(economic, missing_data_fields)
    simulation_stability = _compute_stability(monte_carlo)
    economic_certainty = _clamp(economic.data_confidence * 100)
    historical_similarity = _clamp(_compute_historical_similarity(agent_outputs, economic))

    freshness_map = economic.data_freshness if hasattr(economic, "data_freshness") else {}
    live_count = sum(1 for v in freshness_map.values() if v == "live")
    total_count = max(len(freshness_map), 1)
    data_freshness_score = _clamp((live_count / total_count) * 100)
    data_completeness_score = _clamp(economic.data_completeness * 100 if hasattr(economic, "data_completeness") else 50)

    missing_penalty = len(missing_data_fields) * 5
    freshness_penalty = (1 - live_count / total_count) * 10

    raw = (
        agent_agreement * 0.20
        + data_quality * 0.20
        + simulation_stability * 0.15
        + economic_certainty * 0.10
        + historical_similarity * 0.05
        + data_freshness_score * 0.15
        + data_completeness_score * 0.15
    ) * (1 - missing_penalty / 100) * (1 - freshness_penalty / 100)

    overall = _clamp(raw)

    per_aspect = {}
    for n in NODES:
        scores = [ao.score for ao in agent_outputs.values() if n.lower() in ao.agent_name.lower() or n in ao.year_scores]
        per_aspect[n] = _clamp(sum(scores) / len(scores)) if scores else 50

    per_agent = {name: _clamp(ao.confidence * 100) for name, ao in agent_outputs.items()}

    uncertainty_drivers = []
    if agent_agreement < 40:
        uncertainty_drivers.append("High disagreement between agents")
    if data_quality < 50:
        uncertainty_drivers.append("Low data quality from economic sources")
    if simulation_stability < 40:
        uncertainty_drivers.append("Wide variance in Monte Carlo simulations")
    if economic_certainty < 50:
        uncertainty_drivers.append("Uncertain economic forecasts")
    if data_freshness_score < 40:
        uncertainty_drivers.append("Stale data - fewer than half data sources have live updates")
    if data_completeness_score < 40:
        uncertainty_drivers.append("Incomplete data coverage across sources")
    if missing_penalty > 15:
        uncertainty_drivers.append(f"Missing data for {len(missing_data_fields)} field(s)")

    tier = "high" if overall >= 75 else "medium" if overall >= 50 else "low"

    logger.info("[ConfidenceEngine] overall=%.1f agreement=%.1f data=%.1f stability=%.1f certainty=%.1f freshness=%.1f completeness=%.1f",
                overall, agent_agreement, data_quality, simulation_stability, economic_certainty, data_freshness_score, data_completeness_score)
    logger.info("[ConfidenceEngine] Tier: %s, Uncertainty drivers: %s", tier, uncertainty_drivers)

    return ConfidenceBreakdown(
        overall=round(overall, 1),
        agent_agreement=round(agent_agreement, 1),
        data_quality=round(data_quality, 1),
        simulation_stability=round(simulation_stability, 1),
        economic_certainty=round(economic_certainty, 1),
        historical_similarity=round(historical_similarity, 1),
        missing_data_penalty=round(missing_penalty, 1),
        data_freshness_score=round(data_freshness_score, 1),
        data_completeness_score=round(data_completeness_score, 1),
        per_aspect=per_aspect,
        per_agent=per_agent,
        uncertainty_drivers=uncertainty_drivers,
        tier=tier,
    )


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _compute_agent_agreement(agent_outputs: Dict[str, AgentOutput]) -> float:
    scores = [ao.score for ao in agent_outputs.values()]
    if len(scores) < 2:
        return 50.0
    mu = sum(scores) / len(scores)
    variance = sum((s - mu) ** 2 for s in scores) / len(scores)
    std = math.sqrt(variance)
    cv = std / max(mu, 1)
    return _clamp(100 - cv * 50)


def _compute_data_quality(economic: EconomicData, missing: List[str]) -> float:
    base = economic.data_confidence * 100
    penalty = len(missing) * 8
    return _clamp(base - penalty)


def _compute_stability(mc: MonteCarloResult) -> float:
    happiness_std = mc.node_distributions.get("happiness", {}).get("std", 15)
    mu = mc.node_distributions.get("happiness", {}).get("mean", 50)
    cv = happiness_std / max(mu, 1)
    return _clamp(100 - cv * 100)


def _compute_historical_similarity(agent_outputs: Dict[str, AgentOutput], economic: EconomicData) -> float:
    confs = [ao.confidence for ao in agent_outputs.values()]
    avg_conf = sum(confs) / len(confs) if confs else 0.5
    return _clamp(avg_conf * 80)
