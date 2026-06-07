"""
Parallel agent execution nodes — run all specialist agents concurrently.
"""
import json
import logging
import time
from typing import Any, Dict, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from graph.state import SimulationState, SimulationPhase, AgentOutput
from graph.agents.economic import EconomicAgent
from graph.agents.career import CareerAgent
from graph.agents.financial import FinancialAgent
from graph.agents.health import HealthAgent
from graph.agents.relationship import RelationshipAgent
from graph.agents.opportunity import OpportunityAgent
from graph.agents.risk import RiskAgent
from graph.agents.time import TimeAgent
from graph.agents.happiness import HappinessAgent
from graph.agents.identity import IdentityAgent
from graph.agents.strategic import StrategicAgent
from graph.agents.lifestyle import LifestyleAgent
from graph.nodes.orchestration import extract_economic_data, prepare_economic_context

# Domain → relevant agent names mapping
_DOMAIN_AGENTS = {
    "educational": ["strategic", "risk", "health", "happiness", "opportunity", "identity"],
    "career": ["economic", "career", "financial", "strategic", "risk", "opportunity", "health", "happiness", "identity", "time", "lifestyle", "relationship"],
    "business": ["opportunity", "financial", "risk", "strategic", "time", "lifestyle"],
    "financial": ["financial", "economic", "risk", "strategic", "happiness", "opportunity"],
    "relocation": ["opportunity", "risk", "happiness", "lifestyle", "economic", "strategic"],
    "relationship": ["relationship", "happiness", "risk", "lifestyle", "identity", "strategic"],
    "health": ["health", "happiness", "risk", "strategic", "identity"],
    "lifestyle": ["lifestyle", "happiness", "risk", "strategic", "identity", "relationship"],
    "general": ["strategic", "risk", "happiness", "opportunity", "identity", "lifestyle"],
}

_ALL_AGENT_FUNCTIONS = {}

logger = logging.getLogger(__name__)


def run_economic_agent(state: SimulationState) -> SimulationState:
    _log_agent_start("economic")
    start = time.time()
    try:
        agent = EconomicAgent()
        eco_data = extract_economic_data(state)
        memory_ctx = _get_memory_context(state)
        result = agent.analyze(state.decision, state.context, eco_data,
                               core_variables=state.context.get("_computed", {}),
                               memory_context=memory_ctx)
        latency = (time.time() - start) * 1000
        _log_agent_end("economic", "success", latency)
        state.agent_outputs["economic"] = AgentOutput(
            agent_name="economic",
            output=result,
            confidence=result.get("confidence", 0.7),
            latency_ms=latency,
            model_used="llm",
        )
    except Exception as exc:
        latency = (time.time() - start) * 1000
        _log_agent_end("economic", "error", latency, str(exc))
        logger.error("[Node] Economic Agent failed: %s", exc)
        state.agent_outputs["economic"] = AgentOutput(
            agent_name="economic", output={}, confidence=0.0,
            latency_ms=latency, model_used="fallback", error=str(exc),
        )
    return state


def run_career_agent(state: SimulationState) -> SimulationState:
    _log_agent_start("career")
    start = time.time()
    try:
        agent = CareerAgent()
        eco_data = extract_economic_data(state)
        memory_ctx = _get_memory_context(state)
        result = agent.analyze(state.decision, state.context, eco_data,
                               memory_context=memory_ctx)
        latency = (time.time() - start) * 1000
        _log_agent_end("career", "success", latency)
        state.agent_outputs["career"] = AgentOutput(
            agent_name="career", output=result, confidence=result.get("confidence", 0.7),
            latency_ms=latency, model_used="llm",
        )
    except Exception as exc:
        latency = (time.time() - start) * 1000
        _log_agent_end("career", "error", latency, str(exc))
        logger.error("[Node] Career Agent failed: %s", exc)
        state.agent_outputs["career"] = AgentOutput(
            agent_name="career", output={}, confidence=0.0,
            latency_ms=latency, model_used="fallback", error=str(exc),
        )
    return state


def run_financial_agent(state: SimulationState) -> SimulationState:
    _log_agent_start("financial")
    start = time.time()
    try:
        agent = FinancialAgent()
        eco_data = extract_economic_data(state)
        cvars = state.context.get("_computed", {})
        memory_ctx = _get_memory_context(state)
        result = agent.analyze(state.decision, state.context, eco_data,
                               core_variables=cvars, memory_context=memory_ctx)
        latency = (time.time() - start) * 1000
        _log_agent_end("financial", "success", latency)
        state.agent_outputs["financial"] = AgentOutput(
            agent_name="financial", output=result, confidence=result.get("confidence", 0.7),
            latency_ms=latency, model_used="llm",
        )
    except Exception as exc:
        latency = (time.time() - start) * 1000
        _log_agent_end("financial", "error", latency, str(exc))
        logger.error("[Node] Financial Agent failed: %s", exc)
        state.agent_outputs["financial"] = AgentOutput(
            agent_name="financial", output={}, confidence=0.0,
            latency_ms=latency, model_used="fallback", error=str(exc),
        )
    return state


def run_health_agent(state: SimulationState) -> SimulationState:
    _log_agent_start("health")
    start = time.time()
    try:
        agent = HealthAgent()
        eco_data = extract_economic_data(state)
        cvars = state.context.get("_computed", {})
        memory_ctx = _get_memory_context(state)
        result = agent.analyze(state.decision, state.context, eco_data,
                               core_variables=cvars, memory_context=memory_ctx)
        latency = (time.time() - start) * 1000
        _log_agent_end("health", "success", latency)
        state.agent_outputs["health"] = AgentOutput(
            agent_name="health", output=result, confidence=result.get("confidence", 0.7),
            latency_ms=latency, model_used="llm",
        )
    except Exception as exc:
        latency = (time.time() - start) * 1000
        _log_agent_end("health", "error", latency, str(exc))
        logger.error("[Node] Health Agent failed: %s", exc)
        state.agent_outputs["health"] = AgentOutput(
            agent_name="health", output={}, confidence=0.0,
            latency_ms=latency, model_used="fallback", error=str(exc),
        )
    return state


def run_relationship_agent(state: SimulationState) -> SimulationState:
    _log_agent_start("relationship")
    start = time.time()
    try:
        agent = RelationshipAgent()
        eco_data = extract_economic_data(state)
        cvars = state.context.get("_computed", {})
        memory_ctx = _get_memory_context(state)
        result = agent.analyze(state.decision, state.context, eco_data,
                               core_variables=cvars, memory_context=memory_ctx)
        latency = (time.time() - start) * 1000
        _log_agent_end("relationship", "success", latency)
        state.agent_outputs["relationship"] = AgentOutput(
            agent_name="relationship", output=result, confidence=result.get("confidence", 0.7),
            latency_ms=latency, model_used="llm",
        )
    except Exception as exc:
        latency = (time.time() - start) * 1000
        _log_agent_end("relationship", "error", latency, str(exc))
        logger.error("[Node] Relationship Agent failed: %s", exc)
        state.agent_outputs["relationship"] = AgentOutput(
            agent_name="relationship", output={}, confidence=0.0,
            latency_ms=latency, model_used="fallback", error=str(exc),
        )
    return state


def run_opportunity_agent(state: SimulationState) -> SimulationState:
    _log_agent_start("opportunity")
    start = time.time()
    try:
        agent = OpportunityAgent()
        eco_data = extract_economic_data(state)
        memory_ctx = _get_memory_context(state)
        result = agent.analyze(state.decision, state.context, eco_data,
                               core_variables=state.context.get("_computed", {}),
                               memory_context=memory_ctx)
        latency = (time.time() - start) * 1000
        _log_agent_end("opportunity", "success", latency)
        state.agent_outputs["opportunity"] = AgentOutput(
            agent_name="opportunity", output=result, confidence=result.get("confidence", 0.7),
            latency_ms=latency, model_used="llm",
        )
    except Exception as exc:
        latency = (time.time() - start) * 1000
        _log_agent_end("opportunity", "error", latency, str(exc))
        logger.error("[Node] Opportunity Agent failed: %s", exc)
        state.agent_outputs["opportunity"] = AgentOutput(
            agent_name="opportunity", output={}, confidence=0.0,
            latency_ms=latency, model_used="fallback", error=str(exc),
        )
    return state


def run_risk_agent(state: SimulationState) -> SimulationState:
    _log_agent_start("risk")
    start = time.time()
    try:
        agent = RiskAgent()
        eco_data = extract_economic_data(state)
        cvars = state.context.get("_computed", {})
        result = agent.analyze(state.decision, state.context, eco_data, core_variables=cvars)
        latency = (time.time() - start) * 1000
        _log_agent_end("risk", "success", latency)
        state.agent_outputs["risk"] = AgentOutput(
            agent_name="risk", output=result, confidence=result.get("confidence", 0.7),
            latency_ms=latency, model_used="deterministic",
        )
    except Exception as exc:
        latency = (time.time() - start) * 1000
        _log_agent_end("risk", "error", latency, str(exc))
        state.agent_outputs["risk"] = AgentOutput(
            agent_name="risk", output={}, confidence=0.0,
            latency_ms=latency, model_used="fallback", error=str(exc),
        )
    return state


def run_time_agent(state: SimulationState) -> SimulationState:
    _log_agent_start("time")
    start = time.time()
    try:
        agent = TimeAgent()
        eco_data = extract_economic_data(state)
        result = agent.analyze(state.decision, state.context, eco_data)
        latency = (time.time() - start) * 1000
        _log_agent_end("time", "success", latency)
        state.agent_outputs["time"] = AgentOutput(
            agent_name="time", output=result, confidence=result.get("confidence", 0.7),
            latency_ms=latency, model_used="deterministic",
        )
    except Exception as exc:
        latency = (time.time() - start) * 1000
        _log_agent_end("time", "error", latency, str(exc))
        state.agent_outputs["time"] = AgentOutput(
            agent_name="time", output={}, confidence=0.0,
            latency_ms=latency, model_used="fallback", error=str(exc),
        )
    return state


def run_happiness_agent(state: SimulationState) -> SimulationState:
    _log_agent_start("happiness")
    start = time.time()
    try:
        agent = HappinessAgent()
        eco_data = extract_economic_data(state)
        cvars = state.context.get("_computed", {})
        result = agent.analyze(state.decision, state.context, eco_data, core_variables=cvars)
        latency = (time.time() - start) * 1000
        _log_agent_end("happiness", "success", latency)
        state.agent_outputs["happiness"] = AgentOutput(
            agent_name="happiness", output=result, confidence=result.get("confidence", 0.7),
            latency_ms=latency, model_used="deterministic",
        )
    except Exception as exc:
        latency = (time.time() - start) * 1000
        _log_agent_end("happiness", "error", latency, str(exc))
        state.agent_outputs["happiness"] = AgentOutput(
            agent_name="happiness", output={}, confidence=0.0,
            latency_ms=latency, model_used="fallback", error=str(exc),
        )
    return state


def run_identity_agent(state: SimulationState) -> SimulationState:
    _log_agent_start("identity")
    start = time.time()
    try:
        agent = IdentityAgent()
        eco_data = extract_economic_data(state)
        result = agent.analyze(state.decision, state.context, eco_data)
        latency = (time.time() - start) * 1000
        _log_agent_end("identity", "success", latency)
        state.agent_outputs["identity"] = AgentOutput(
            agent_name="identity", output=result, confidence=result.get("confidence", 0.7),
            latency_ms=latency, model_used="deterministic",
        )
    except Exception as exc:
        latency = (time.time() - start) * 1000
        _log_agent_end("identity", "error", latency, str(exc))
        state.agent_outputs["identity"] = AgentOutput(
            agent_name="identity", output={}, confidence=0.0,
            latency_ms=latency, model_used="fallback", error=str(exc),
        )
    return state


def run_strategic_agent(state: SimulationState) -> SimulationState:
    _log_agent_start("strategic")
    start = time.time()
    try:
        agent = StrategicAgent()
        eco_data = extract_economic_data(state)
        result = agent.analyze(state.decision, state.context, eco_data)
        latency = (time.time() - start) * 1000
        _log_agent_end("strategic", "success", latency)
        state.agent_outputs["strategic"] = AgentOutput(
            agent_name="strategic", output=result, confidence=result.get("confidence", 0.7),
            latency_ms=latency, model_used="deterministic",
        )
    except Exception as exc:
        latency = (time.time() - start) * 1000
        _log_agent_end("strategic", "error", latency, str(exc))
        state.agent_outputs["strategic"] = AgentOutput(
            agent_name="strategic", output={}, confidence=0.0,
            latency_ms=latency, model_used="fallback", error=str(exc),
        )
    return state


def run_lifestyle_agent(state: SimulationState) -> SimulationState:
    _log_agent_start("lifestyle")
    start = time.time()
    try:
        agent = LifestyleAgent()
        eco_data = extract_economic_data(state)
        cvars = state.context.get("_computed", {})
        result = agent.analyze(state.decision, state.context, eco_data, core_variables=cvars)
        latency = (time.time() - start) * 1000
        _log_agent_end("lifestyle", "success", latency)
        state.agent_outputs["lifestyle"] = AgentOutput(
            agent_name="lifestyle", output=result, confidence=result.get("confidence", 0.7),
            latency_ms=latency, model_used="deterministic",
        )
    except Exception as exc:
        latency = (time.time() - start) * 1000
        _log_agent_end("lifestyle", "error", latency, str(exc))
        state.agent_outputs["lifestyle"] = AgentOutput(
            agent_name="lifestyle", output={}, confidence=0.0,
            latency_ms=latency, model_used="fallback", error=str(exc),
        )
    return state


def run_all_parallel_agents(state: SimulationState) -> SimulationState:
    # Determine domain from parsed decision
    parsed = state.context.get("_parsed_decision", {})
    raw_type = parsed.get("decision_type", "general") if isinstance(parsed, dict) else "general"
    domain = raw_type if raw_type in _DOMAIN_AGENTS else "general"
    agent_names = _DOMAIN_AGENTS.get(domain, _DOMAIN_AGENTS["general"])

    logger.info("[Node] Domain=%s — running %d agents: %s", domain, len(agent_names), agent_names)
    start = time.time()

    # Register agent runner functions once
    global _ALL_AGENT_FUNCTIONS
    if not _ALL_AGENT_FUNCTIONS:
        _ALL_AGENT_FUNCTIONS.update({
            "economic": run_economic_agent,
            "career": run_career_agent,
            "financial": run_financial_agent,
            "health": run_health_agent,
            "relationship": run_relationship_agent,
            "opportunity": run_opportunity_agent,
            "risk": run_risk_agent,
            "time": run_time_agent,
            "happiness": run_happiness_agent,
            "identity": run_identity_agent,
            "strategic": run_strategic_agent,
            "lifestyle": run_lifestyle_agent,
        })

    with ThreadPoolExecutor(max_workers=len(agent_names)) as executor:
        futures = {}
        for name in agent_names:
            runner = _ALL_AGENT_FUNCTIONS.get(name)
            if runner:
                futures[executor.submit(runner, state)] = name
        for future in as_completed(futures):
            agent_name = futures[future]
            try:
                future.result()
                logger.info("[Node] %s agent completed", agent_name)
            except Exception as exc:
                logger.error("[Node] %s agent thread failed: %s", agent_name, exc)

    # Store domain in context for later use
    state.context["_domain"] = domain
    state.phase = SimulationPhase.DEBATE
    logger.info("[Node] %d agents completed in %.0fms", len(agent_names), (time.time() - start) * 1000)
    return state


def _log_agent_start(name: str):
    logger.info(json.dumps({"event": "agent_start", "agent": name, "timestamp": time.time()}))


def _log_agent_end(name: str, status: str, latency_ms: float, model: str = ""):
    logger.info(json.dumps({
        "event": "agent_end", "agent": name, "status": status,
        "latency_ms": round(latency_ms, 1), "model": model,
    }))


def _get_memory_context(state: SimulationState) -> str:
    if state.memory_context:
        mc = state.memory_context
        if isinstance(mc, dict):
            return json.dumps(mc, indent=2, default=str)
        return str(mc)
    return "No prior context available."
