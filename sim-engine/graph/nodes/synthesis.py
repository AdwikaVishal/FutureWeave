"""
Synthesis node — combines all agent outputs into final recommendation.
"""
import logging
import time

from graph.state import SimulationState, SimulationPhase

logger = logging.getLogger(__name__)


def synthesis_node(state: SimulationState) -> SimulationState:
    logger.info("[Node] Running Synthesis Agent")
    state.phase = SimulationPhase.SYNTHESIS
    start = time.time()

    from graph.agents.synthesis import SynthesisAgent

    agent_outputs = {}
    for name in ["economic", "career", "financial", "health", "relationship", "opportunity"]:
        ao = state.agent_outputs.get(name)
        if ao:
            agent_outputs[name] = ao.output

    debate_output = state.agent_outputs.get("debate")
    debate_result = debate_output.output if debate_output else {}

    timelines_raw = {}
    for tl_key, tl_state in state.timelines.items():
        timelines_raw[tl_key] = {
            tl_key: {
                "archetype": tl_state.archetype,
                "final_outcome": tl_state.final_outcome or {},
            }
        }

    critic_result = state.critic_result or {"evaluations": [], "verdict": "INSUFFICIENT_DATA"}

    future_self_data = {}
    for tl_key, fs_state in state.future_selves.items():
        future_self_data[tl_key] = {
            "name": fs_state.persona,
            "biography": fs_state.biography,
            "perspectives": fs_state.perspectives,
        }

    try:
        agent = SynthesisAgent()
        result = agent.synthesize(
            state.decision,
            state.context,
            agent_outputs,
            debate_result,
            timelines_raw,
            critic_result,
            future_self_data,
            state.monte_carlo_results,
        )
        state.synthesis_result = result
        logger.info("[Synthesis] Complete with recommendation: %s", result.get("recommendation", {}).get("primary_path", "N/A"))
    except Exception as exc:
        logger.error("[Synthesis] Failed: %s", exc)
        state.synthesis_result = {"error": str(exc)}

    state.phase = SimulationPhase.COMPLETE
    return state
