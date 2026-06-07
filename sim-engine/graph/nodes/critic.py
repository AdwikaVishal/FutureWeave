"""
Critic node — validates timeline consistency and quality.
"""
import logging
import time

from graph.state import SimulationState, SimulationPhase

logger = logging.getLogger(__name__)


def critic_node(state: SimulationState) -> SimulationState:
    logger.info("[Node] Running Critic Agent")
    state.phase = SimulationPhase.CRITIQUE
    start = time.time()

    from graph.agents.critic import CriticAgent

    eco_data = {
        "gdp_growth": state.economic.gdp_growth,
        "inflation_cpi": state.economic.inflation_cpi,
        "unemployment_rate": state.economic.unemployment_rate,
        "salary_entry_lpa": "6.3-12.7",
        "salary_mid_lpa": "15.8-31.7",
        "salary_senior_lpa": "31.7-84.4",
    }

    timelines_raw = {}
    for tl_key, tl_state in state.timelines.items():
        timelines_raw[tl_key] = {
            tl_key: {
                "archetype": tl_state.archetype,
                "final_outcome": tl_state.final_outcome or {},
            }
        }

    try:
        agent = CriticAgent()
        result = agent.evaluate(
            state.decision,
            state.context,
            eco_data,
            timelines_raw,
            None,
        )
        logger.info("[Critic] Evaluation complete with verdict: %s", result.get("verdict", "UNKNOWN"))
        if result.get("verdict") == "INSUFFICIENT_DATA":
            logger.warning("[Critic] Verdict is INSUFFICIENT_DATA — LLM was unavailable, critique is limited")
        state.critic_result = result
    except Exception as exc:
        logger.error("[Critic] Failed: %s", exc)
        result = {
            "evaluations": [],
            "global_issues": ["Critic evaluation unavailable"],
            "verdict": "INSUFFICIENT_DATA",
        }
        state.critic_result = result

    state.phase = SimulationPhase.FUTURE_SELF
    return state
