"""
Main simulation workflow — entry point for running the full FutureWeave simulation.
"""
import json
import logging
import time
from typing import Any, Dict, Optional

from graph.builder import build_default_graph, create_simulation
from graph.state import SimulationState, SimulationPhase

logger = logging.getLogger(__name__)


def run_simulation(
    decision: str,
    context: dict,
    economic_override: Optional[dict] = None,
    memory_context: Optional[dict] = None,
    enable_monte_carlo: bool = False,
    monte_carlo_iterations: int = 100,
) -> dict:
    logger.info("[Workflow] Starting simulation: %s", decision[:80])

    from llm_client import any_provider_healthy
    if not any_provider_healthy():
        logger.warning(
            "[Workflow] No LLM providers configured — all agents will use deterministic fallbacks. "
            "Set at least one API key (OPENAI_API_KEY, GEMINI_API_KEY, etc.) for LLM-powered outputs."
        )

    state = create_simulation(decision, context)

    if economic_override:
        for key, value in economic_override.items():
            if hasattr(state.economic, key):
                setattr(state.economic, key, value)

    if memory_context:
        state.memory_context = memory_context

    graph = build_default_graph()
    final_state = graph.execute(state)

    result = _state_to_result(final_state)
    return result


def _compute_confidence(name: str, ao) -> float:
    """Compute confidence from data quality, source availability, model agreement, and simulation stability."""
    if ao.error:
        return 0.0
    if ao.model_used in ("fallback", "deterministic"):
        return 0.1
    if ao.model_used == "llm" and ao.confidence is not None:
        confidence = float(ao.confidence)
        if 0 <= confidence <= 1:
            return round(confidence, 2)
        return round(min(1.0, max(0.0, confidence / 100.0)), 2)
    return 0.5


def _build_reasoning(name: str, output: dict, ao) -> str:
    """Build meaningful reasoning text from available signals."""
    reasoning = output.get("reasoning")
    if reasoning and isinstance(reasoning, str) and len(reasoning) > 10:
        return reasoning
    key_insights = output.get("key_insights", [])
    if isinstance(key_insights, list) and key_insights:
        first = key_insights[0]
        if isinstance(first, str) and len(first) > 10:
            return first
        return str(first)
    impact_factors = output.get("impact_factors", [])
    if isinstance(impact_factors, list) and impact_factors:
        first = impact_factors[0]
        if isinstance(first, dict):
            desc = first.get("description") or first.get("factor") or str(first)
            return str(desc)[:200]
        return str(first)[:200]
    summary = output.get("summary")
    if summary and isinstance(summary, str) and len(summary) > 10:
        return summary
    verdict = output.get("verdict")
    if verdict and isinstance(verdict, str) and verdict.lower() not in ("", "neutral", "positive", "negative"):
        return str(verdict)
    impact = output.get("impact")
    if isinstance(impact, str) and len(impact) > 10:
        return impact
    if ao.model_used in ("fallback", "deterministic"):
        return "Deterministic estimate (LLM unavailable)"
    return "Analysis complete"


def _normalize_agent_output(name: str, ao) -> dict:
    """Flatten an AgentOutput into a clean dict with score/confidence/reasoning."""
    output = ao.output if isinstance(ao.output, dict) else {}
    score = output.get("score")
    if score is None:
        for key in ("financial_risk_score", "burnout_risk_forecast",
                     "long_term_wellbeing_score", "wealth_growth_score",
                     "opportunity_score_forecast"):
            val = output.get(key)
            if val is not None:
                if isinstance(val, list) and val and isinstance(val[-1], dict):
                    extracted = val[-1].get("score")
                    if extracted is not None:
                        score = extracted
                        break
                elif isinstance(val, (int, float)):
                    score = val
                    break
    if score is None or not isinstance(score, (int, float)):
        score = 50
    score = round(float(score), 1)
    reasoning = _build_reasoning(name, output, ao)
    verdict = output.get("verdict")
    if not isinstance(verdict, str):
        impact = output.get("impact")
        verdict = str(impact) if impact else ""
    confidence = _compute_confidence(name, ao)
    return {
        "name": name,
        "score": score,
        "confidence": confidence,
        "reasoning": str(reasoning),
        "verdict": str(verdict),
        "evidence": output.get("evidence", []),
        "source_attribution": output.get("source_attribution", []),
        "option_rankings": output.get("option_rankings", []),
        "per_option_scores": output.get("per_option_scores", {}),
        "impact_factors": output.get("impact_factors", []),
        "impact": output.get("impact", "neutral"),
        "error": ao.error,
        "model_used": ao.model_used,
    }


def _state_to_result(state: SimulationState) -> dict:
    agent_outputs = {}
    for name, ao in state.agent_outputs.items():
        entry = {
            "confidence": round(ao.confidence, 2) if ao.confidence is not None else 0.0,
            "latency_ms": round(ao.latency_ms, 1),
            "error": ao.error,
            "agent_name": ao.agent_name,
        }
        if isinstance(ao.output, dict):
            entry.update(ao.output)
        else:
            entry["output"] = ao.output
        agent_outputs[name] = entry

    # Build clean agents list for frontend
    agents_list = []
    for name, ao in state.agent_outputs.items():
        agents_list.append(_normalize_agent_output(name, ao))

    # Top 4 agents by score for main page insights
    agents_list.sort(key=lambda a: a["score"], reverse=True)
    main_page_insights = agents_list[:4]

    YEAR_MAP = {
        "year1": "Year1", "year2": "Year2", "year3": "Year3",
        "year5": "Year5", "year7": "Year7", "year10": "Year10",
    }
    FRONTEND_YEARS = ["Year1", "Year3", "Year5", "Year10"]

    timelines_result = {}
    causal_data = {}
    for tl_key, tl_state in state.timelines.items():
        base = {
            "label": tl_state.label,
            "archetype": tl_state.archetype,
            "final_outcome": tl_state.final_outcome,
        }
        raw = state.timeline_raw_data.get(tl_key, {})
        year_narratives = {}
        year_scores = {}
        for raw_key, fe_key in YEAR_MAP.items():
            year_entry = raw.get(raw_key, {})
            narrative = ""
            scores = {}
            if isinstance(year_entry, dict):
                narrative = year_entry.get("narrative", "")
                scores = year_entry.get("scores", {})
            elif isinstance(year_entry, str):
                narrative = year_entry
            year_narratives[fe_key] = narrative
            if scores:
                year_scores[fe_key] = {k: round(float(v), 1) for k, v in scores.items()}
        timelines_result[tl_key] = {**base, **year_narratives}
        causal_data[tl_key] = year_scores

    future_selves_result = {}
    for tl_key, fs_state in state.future_selves.items():
        future_selves_result[tl_key] = {
            "persona": fs_state.persona,
            "biography": fs_state.biography,
            "perspectives": fs_state.perspectives,
        }

    domain = state.context.get("_domain", "general")

    # Data quality from working/total sources
    from services.sync_data import get_data_quality
    dq = get_data_quality()
    data_quality_score = dq.get("score", 0.25)

    llm_calls = sum(1 for ao in state.agent_outputs.values() if ao.model_used == "llm")
    total_agents = max(len(state.agent_outputs), 1)
    fallback_ratio = 1.0 - (llm_calls / total_agents)

    # Confidence = data_quality*0.4 + source_availability*0.2 + agent_agreement*0.3 + simulation_stability*0.1
    agent_confidence_values = [
        _compute_confidence(n, ao) for n, ao in state.agent_outputs.items()
    ]
    agent_agreement = sum(c for c in agent_confidence_values if c > 0.5) / max(len(agent_confidence_values), 1) if agent_confidence_values else 0.5
    sim_stability = 0.8 if not state.error else 0.3
    overall_confidence = round(
        data_quality_score * 0.4 +
        data_quality_score * 0.2 +
        agent_agreement * 0.3 +
        sim_stability * 0.1,
        2,
    )
    data_confidence = round(max(10, min(95, 95 - (fallback_ratio * 60))))

    return {
        "simulation_id": state.simulation_id,
        "decision": state.decision,
        "domain": domain,
        "phase": state.phase.value,
        "error": state.error,
        "latency_ms": round(state.latency_ms, 1),
        "overall_confidence": overall_confidence,
        "data_quality": {
            "score": data_quality_score,
            "working": dq.get("working", 0),
            "total": dq.get("total", 0),
            "percent": dq.get("percent", 0),
        },
        "data_confidence": data_confidence,
        "agent_outputs": agent_outputs,
        "agents": agents_list,
        "main_page_insights": main_page_insights,
        "timelines": timelines_result,
        "causal_data": causal_data,
        "archetype_labels": {tl: state.timelines[tl].archetype for tl in state.timelines},
        "future_selves": future_selves_result,
        "synthesis": state.synthesis_result,
        "monte_carlo": state.monte_carlo_results,
        "events": state.events,
        "economic": {
            "gdp_growth": round(state.economic.gdp_growth, 2) if state.economic.gdp_growth is not None else None,
            "inflation_cpi": round(state.economic.inflation_cpi, 2) if state.economic.inflation_cpi is not None else None,
            "unemployment_rate": round(state.economic.unemployment_rate, 2) if state.economic.unemployment_rate is not None else None,
        },
    }
