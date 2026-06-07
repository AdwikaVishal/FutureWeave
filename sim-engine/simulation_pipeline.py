"""
New Simulation Pipeline — decision-type-aware, no global economic snapshot.

Flow:
  Decision
    ↓
  Classifier → DecisionType
    ↓
  Router → verify provider mapping
    ↓
  Provider → collect decision-specific data
    ↓
  ContextBuilder → build anchors + initial scores
    ↓
  TimelineGenerator → project scores over years
    ↓
  Agents → evaluate across universal dimensions
    ↓
  Recommendation + Monte Carlo
"""

import json
import logging
from typing import Any

from decision_type import DecisionType
from decision_parser import parse_decision
from decision_router import DecisionRouter, route_decision
from providers.base import ProviderContext
from providers.registry import get_provider
from contexts.registry import get_context_builder
from timelines.registry import get_timeline_generator
from monte_carlo import monte_carlo_for_type
from agents.universal.opportunity import OpportunityAgent
from agents.universal.risk import RiskAgent
from agents.universal.financial import FinancialAgent
from agents.universal.learning import LearningAgent
from agents.universal.health import HealthAgent
from agents.universal.relationship import RelationshipAgent
from agents.universal.lifestyle import LifestyleAgent
from agents.universal.future_self import FutureSelfAgent

logger = logging.getLogger(__name__)

ARCHETYPE_LABELS = {
    "A": "The Settler (Conservative)",
    "B": "The Climber (Balanced)",
    "C": "The Gambler (Aggressive)",
}

YEARS = ["Year1", "Year3", "Year5", "Year10"]


def run_pipeline(decision: str, context: dict, **kwargs) -> dict:
    # ── 1. Parse ───────────────────────────────────────────────────────
    parsed = parse_decision(decision)
    dt = DecisionType(parsed.decision_type) if parsed.decision_type in DecisionType._value2member_map_ else DecisionType.GENERAL

    # ── 2. Classifier ──────────────────────────────────────────────────
    from services.decision_classifier import classify_decision
    profile = classify_decision(decision, context)
    logger.info("[Pipeline] Classified as: %s (confidence=%s)", dt.value, profile.confidence)

    # ── 3. Route + Verify ──────────────────────────────────────────────
    route_info = route_decision(dt)

    # ── 4. Provider — NO economic snapshot, NO worldbank for edu ─────
    provider = get_provider(dt)
    pctx = ProviderContext(
        decision=decision,
        options=parsed.options,
        location=context.get("location", "India"),
        raw_context=context,
    )
    provider_result = provider.collect(pctx)

    # ── 5. Context Builder ─────────────────────────────────────────────
    builder = get_context_builder(dt)
    anchors = builder.build_anchors(provider_result.context_data)
    initial_scores = builder.build_initial_scores(provider_result.context_data)

    # ── 6. Timeline Generator ──────────────────────────────────────────
    timeline_gen = get_timeline_generator(dt)
    all_causal = timeline_gen.generate(initial_scores, anchors, YEARS)

    # ── 7. Build enriched timelines ────────────────────────────────────
    enriched = {}
    for arch_key in ["A", "B", "C"]:
        tl_key = f"Timeline {arch_key}"
        causal = all_causal.get(arch_key, {})
        enriched[tl_key] = {
            "_causal": causal,
            "_decision_type": dt.value,
        }
        for yr in YEARS:
            yr_scores = causal.get(yr, {})
            top = max(yr_scores.values()) if yr_scores else 50
            if top >= 70:
                narrative = "Strong performance across key metrics."
            elif top >= 50:
                narrative = "Moderate progress — steady improvement expected."
            else:
                narrative = "Challenging period — higher effort needed."
            enriched[tl_key][yr] = narrative

    # ── 8. Universal Agents ────────────────────────────────────────────
    agent_classes = [
        OpportunityAgent, RiskAgent, FinancialAgent, LearningAgent,
        HealthAgent, RelationshipAgent, LifestyleAgent, FutureSelfAgent,
    ]
    agent_outputs = {}
    for agent_cls in agent_classes:
        agent = agent_cls()
        output = agent.evaluate(all_causal, dt.value, anchors)
        agent_outputs[agent.name] = {
            "output": {
                "score": output.score,
                "reasoning": output.reasoning,
                "evidence": output.evidence,
            },
            "confidence": output.confidence,
            "latency_ms": 0,
            "error": None,
        }

    # ── 9. Monte Carlo ────────────────────────────────────────────────
    base_scores = {}
    for arch_key in ["A", "B", "C"]:
        yr10 = all_causal.get(arch_key, {}).get("Year10", {})
        for k, v in yr10.items():
            if isinstance(v, (int, float)):
                base_scores[f"{arch_key}_{k}"] = v
    mc_result = monte_carlo_for_type(dt.value, base_scores)

    # ── 10. Build Recommendation ───────────────────────────────────────
    recommendation = _build_recommendation(agent_outputs, dt.value)

    # ── 11. Assemble Response ──────────────────────────────────────────
    timelines_out = {}
    for arch_key in ["A", "B", "C"]:
        tl_key = f"Timeline {arch_key}"
        tl = enriched.get(tl_key, {})
        narratives = {yr: tl.get(yr, "") for yr in YEARS}
        causal = tl.get("_causal", {})
        timelines_out[tl_key] = {
            "narratives": narratives,
            "scores": causal,
        }

    return {
        "decision": decision,
        "decision_type": dt.value,
        "decision_parsing": {
            "options": parsed.options,
            "type": parsed.decision_type,
            "confidence": parsed.confidence,
        },
        "routing": route_info,
        "archetype_labels": ARCHETYPE_LABELS,
        "timelines": timelines_out,
        "agent_outputs": agent_outputs,
        "monte_carlo": mc_result,
        "recommendation": recommendation,
        "data_confidence": provider_result.confidence,
        "data_warnings": provider_result.warnings,
        "pipeline": "v2",
    }


def _build_recommendation(
    agent_outputs: dict[str, Any],
    decision_type: str,
) -> dict:
    scores = {}
    for name, output in agent_outputs.items():
        scores[name] = output["output"]["score"]

    if not scores:
        return {"winner": "N/A", "reason": "No agent data available.", "confidence": 0}

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_name = ranked[0][0]
    best_score = ranked[0][1]

    summary = f"Best overall outcome: {best_name} ({best_score:.0f}/100). "
    summary += f"Decision type: {decision_type}. "

    if decision_type == "educational":
        summary += "Focus on admission probability, placement outlook, and learning trajectory."
    elif decision_type == "career":
        summary += "Focus on income growth, career progression, and work-life balance."
    elif decision_type == "financial":
        summary += "Focus on returns, risk management, and tax efficiency."
    elif decision_type == "relocation":
        summary += "Focus on visa success, quality of life, and integration."
    elif decision_type == "business":
        summary += "Focus on market fit, funding, and scalability."
    elif decision_type == "health":
        summary += "Focus on treatment success, recovery, and long-term wellbeing."

    return {
        "winner": best_name,
        "score": best_score,
        "reason": summary,
        "confidence": round(sum(v["confidence"] for v in agent_outputs.values()) / len(agent_outputs) * 100, 1),
        "dimension_scores": scores,
    }
