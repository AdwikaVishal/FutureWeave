"""
Event Engine node — generates structured events for each timeline.
"""
import logging
import time

from graph.state import SimulationState, SimulationPhase
from graph.agents.event_engine import EventEngineAgent
from graph.nodes.orchestration import extract_economic_data

logger = logging.getLogger(__name__)


def event_engine_node(state: SimulationState) -> SimulationState:
    logger.info("[Node] Running Event Engine")
    state.phase = SimulationPhase.EVENTS
    start = time.time()

    eco_data = extract_economic_data(state)

    try:
        agent = EventEngineAgent()
        result = agent.generate_events(state.decision, state.context, eco_data)
        events_dict = result.get("events", {})
        state.events = events_dict
        logger.info("[EventEngine] Generated events for %d timelines", len(events_dict))
    except Exception as exc:
        logger.error("[EventEngine] Failed: %s", exc)
        state.events = {}

    state.phase = SimulationPhase.CRITIQUE
    return state
