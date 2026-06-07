"""
Timeline node — generates all three timelines in a single batched LLM call.
"""
import logging
import time
from typing import Any, Dict

from graph.state import SimulationState, SimulationPhase, TimelineState
from graph.agents.timeline_gen import TimelineAgent, TimelineAgentFactory

logger = logging.getLogger(__name__)


def timeline_node(state: SimulationState) -> SimulationState:
    logger.info("[Node] Generating all 3 timelines (batched)")
    state.phase = SimulationPhase.TIMELINE
    start = time.time()

    agent_outputs = {}
    for name in ["economic", "career", "financial", "health", "relationship", "opportunity", "debate"]:
        ao = state.agent_outputs.get(name)
        if ao:
            agent_outputs[name] = ao.output

    debate_result = agent_outputs.get("debate", {"debates": [], "balanced_recommendation": "No debate"})
    events = state.events

    results = TimelineAgentFactory.batch_generate(
        decision=state.decision,
        context=state.context,
        economic_output=agent_outputs.get("economic", {}),
        career_output=agent_outputs.get("career", {}),
        financial_output=agent_outputs.get("financial", {}),
        health_output=agent_outputs.get("health", {}),
        relationship_output=agent_outputs.get("relationship", {}),
        opportunity_output=agent_outputs.get("opportunity", {}),
        debate_resolution=debate_result,
        events=events,
        memory_context=None,
    )

    for tl_key, tl_data in results.items():
        tl = tl_data.get(tl_key, tl_data)
        score = 50
        y10 = tl.get("year10", {})
        if isinstance(y10, dict):
            scores = y10.get("scores", {})
            if scores:
                score = int((scores.get("happiness", 50) + scores.get("income", 50)) / 2)
        state.timelines[tl_key] = TimelineState(
            label=tl_key,
            archetype=tl.get("archetype", "Unknown"),
            years={},
            final_outcome=tl.get("final_outcome"),
        )
        state.timeline_raw_data[tl_key] = tl

    state.phase = SimulationPhase.EVENTS
    logger.info("[Node] All timelines generated in %.0fms", (time.time() - start) * 1000)
    return state
