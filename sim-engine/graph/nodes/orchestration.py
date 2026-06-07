"""
Orchestration node — entry point, validates input, initializes state, dispatches parallel agents.
"""
import json
import logging
import time
import uuid
from typing import Any, Dict

from graph.state import SimulationState, SimulationPhase, EconomicState, CareerState, FinancialState, HealthState, RelationshipState, OpportunityState
from input_validator import is_likely_meaningful
from decision_parser import parse_decision, format_options_for_prompt

logger = logging.getLogger(__name__)


def orchestration_node(state: SimulationState) -> SimulationState:
    logger.info("[Orchestrator] Starting simulation for decision: %s", state.decision[:80])

    state.phase = SimulationPhase.ORCHESTRATION
    state.simulation_id = str(uuid.uuid4())[:8]

    valid, msg = is_likely_meaningful(state.decision)
    if not valid:
        state.phase = SimulationPhase.FAILED
        state.error = f"Invalid input: {msg}"
        return state

    parsed = parse_decision(state.decision)
    state.context["_parsed_decision"] = {
        "question": parsed.question,
        "options": parsed.options,
        "decision_type": parsed.decision_type,
        "confidence": parsed.confidence,
    }
    state.context["_decision_options"] = format_options_for_prompt(parsed)

    state.phase = SimulationPhase.PARALLEL_AGENTS
    return state


def prepare_economic_context(context: dict) -> dict:
    return {
        "age": context.get("age", "unknown"),
        "location": context.get("location", "Bangalore"),
        "role": context.get("role", "software_engineer"),
        "industry": context.get("industry", "technology"),
        "work_hours": context.get("work_hours", 45),
        "risk_tolerance": context.get("risk_tolerance", "moderate"),
        "financial_condition": context.get("financial_condition", "middle class"),
        "interests": context.get("interests", []),
        "goals": context.get("goals", []),
    }


def extract_economic_data(state: SimulationState) -> dict:
    eco = state.economic
    return {
        "gdp_growth": eco.gdp_growth if eco.gdp_growth is not None else 6.49,
        "inflation_cpi": eco.inflation_cpi if eco.inflation_cpi is not None else 4.95,
        "unemployment_rate": eco.unemployment_rate if eco.unemployment_rate is not None else 5.0,
        "salary_growth_pct": eco.salary_growth_pct if eco.salary_growth_pct is not None else 7.5,
        "cost_of_living_index": eco.cost_of_living_index if eco.cost_of_living_index is not None else 65.0,
        "industry_health": eco.industry_health if eco.industry_health is not None else 78.0,
        "automation_risk": eco.automation_risk if eco.automation_risk is not None else 15.0,
        "interest_rate": eco.interest_rate if eco.interest_rate is not None else 6.5,
    }
