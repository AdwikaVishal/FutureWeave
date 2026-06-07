"""
Debate node — resolves conflicts between specialist agents.
"""
import logging
import time
from typing import Any, Dict

from graph.state import SimulationState, SimulationPhase, AgentOutput
from graph.agents.debate import DebateAgent

logger = logging.getLogger(__name__)


def debate_node(state: SimulationState) -> SimulationState:
    logger.info("[Node] Running Debate Agent")
    state.phase = SimulationPhase.DEBATE
    start = time.time()

    agent_outputs = {}
    for name in ["economic", "career", "financial", "health", "relationship", "opportunity"]:
        ao = state.agent_outputs.get(name)
        if ao and ao.output:
            agent_outputs[name] = ao.output

    if len(agent_outputs) < 2:
        logger.warning("[Debate] Only %d agents have outputs — using fallback debate", len(agent_outputs))
        state.debates = _fallback_debates(state.decision, agent_outputs, state.context)
        state.agent_outputs["debate"] = AgentOutput(
            agent_name="debate",
            output={"debates": state.debates, "balanced_recommendation": "Fallback debate based on available agent outputs."},
            confidence=0.5,
            latency_ms=(time.time() - start) * 1000,
            model_used="fallback",
        )
        state.phase = SimulationPhase.TIMELINE
        return state

    try:
        agent = DebateAgent()
        result = agent.resolve(state.decision, agent_outputs)
        latency = (time.time() - start) * 1000
        state.agent_outputs["debate"] = AgentOutput(
            agent_name="debate",
            output=result,
            confidence=result.get("overall_confidence", 0.7),
            latency_ms=latency,
            model_used="llm",
        )
    except Exception as exc:
        logger.error("[Debate] Agent failed: %s", exc)
        state.agent_outputs["debate"] = AgentOutput(
            agent_name="debate",
            output={"debates": [], "balanced_recommendation": "Debate unavailable."},
            confidence=0.0,
            latency_ms=(time.time() - start) * 1000,
            model_used="fallback",
            error=str(exc),
        )

    state.phase = SimulationPhase.TIMELINE
    return state


def _fallback_debates(decision: str, agent_outputs: dict, context: dict) -> list:
    from graph.state import DebateEntry

    debates = []
    agents = list(agent_outputs.keys())

    # Strategic vs Risk debate
    if "career" in agents and "health" in agents:
        career = agent_outputs["career"]
        health = agent_outputs["health"]
        career_score = career.get("score", 50) if isinstance(career, dict) else 50
        health_score = health.get("score", 50) if isinstance(health, dict) else 50
        debates.append(DebateEntry(
            topic="Career growth vs Health tradeoff",
            agent_a="career",
            agent_b="health",
            position_a=f"Career acceleration scores {career_score}/100",
            position_b=f"Health impact scores {health_score}/100 — may be compromised by career intensity",
            resolution="The optimal path explicitly caps work hours and protects recovery time.",
            tradeoff_identified="Short-term career gains may erode long-term wellbeing if health is not protected.",
        ))

    # Financial vs Opportunity debate
    if "financial" in agents and "opportunity" in agents:
        fin = agent_outputs["financial"]
        opp = agent_outputs["opportunity"]
        fin_stability = fin.get("financial_risk_score", 50) if isinstance(fin, dict) else 50
        opp_score = opp.get("score", 50) if isinstance(opp, dict) else 50
        debates.append(DebateEntry(
            topic="Financial stability vs Growth opportunity",
            agent_a="financial",
            agent_b="opportunity",
            position_a=f"Financial stability risk at {fin_stability}/100",
            position_b=f"Growth opportunity at {opp_score}/100",
            resolution="Build financial buffer before pursuing high-risk opportunities.",
            tradeoff_identified="Financial caution may delay high-reward opportunities; timing matters.",
        ))

    # Generic fallback based on decision path
    if not debates:
        debates.append(DebateEntry(
            topic="Strategic direction assessment",
            agent_a="strategic",
            agent_b="risk",
            position_a=f"The decision '{decision[:60]}' offers opportunities for growth and advancement.",
            position_b="Every choice carries inherent uncertainty and tradeoffs.",
            resolution="A balanced approach that acknowledges uncertainty while pursuing opportunity is recommended.",
            tradeoff_identified="Growth requires accepting some degree of uncertainty and risk.",
        ))

    return debates
