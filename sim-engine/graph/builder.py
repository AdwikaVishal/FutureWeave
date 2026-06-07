"""
LangGraph Builder — constructs the FutureWeave simulation graph with parallel execution, memory, retry, and observability.
"""
import logging
import time
from typing import Any, Dict, List, Optional, Callable

from graph.state import SimulationState, SimulationPhase
from graph.nodes.orchestration import orchestration_node
from graph.nodes.parallel_agents import run_all_parallel_agents
from graph.nodes.debate import debate_node
from graph.nodes.timeline import timeline_node
from graph.nodes.events import event_engine_node
from graph.nodes.critic import critic_node
from graph.nodes.future_self import future_self_node
from graph.nodes.synthesis import synthesis_node

logger = logging.getLogger(__name__)


class NodeDefinition:
    def __init__(self, name: str, fn: Callable, retries: int = 2, timeout_ms: int = 60000):
        self.name = name
        self.fn = fn
        self.retries = retries
        self.timeout_ms = timeout_ms


class SimulationGraph:
    def __init__(self):
        self.nodes: Dict[str, NodeDefinition] = {}
        self.edges: List[tuple] = []
        self.observers: List[Callable] = []

    def add_node(self, name: str, fn: Callable, retries: int = 2, timeout_ms: int = 60000):
        self.nodes[name] = NodeDefinition(name, fn, retries, timeout_ms)

    def add_edge(self, from_node: str, to_node: str):
        self.edges.append((from_node, to_node))

    def add_observer(self, observer: Callable):
        self.observers.append(observer)

    def _notify_observers(self, phase: str, state: SimulationState):
        for obs in self.observers:
            try:
                obs(phase, state)
            except Exception as exc:
                logger.warning("[Graph] Observer failed: %s", exc)

    def _execute_node(self, node_def: NodeDefinition, state: SimulationState) -> SimulationState:
        last_error = None
        for attempt in range(node_def.retries + 1):
            try:
                start = time.time()
                result = node_def.fn(state)
                elapsed = (time.time() - start) * 1000
                logger.info("[Graph] Node '%s' completed in %.0fms (attempt %d)", node_def.name, elapsed, attempt + 1)
                state.latency_ms += elapsed
                result.phase = self._next_phase(node_def.name)
                return result
            except Exception as exc:
                last_error = exc
                logger.warning("[Graph] Node '%s' failed attempt %d/%d: %s", node_def.name, attempt + 1, node_def.retries + 1, exc)
                if attempt < node_def.retries:
                    continue
        state.error = str(last_error)
        state.phase = SimulationPhase.FAILED
        return state

    def _next_phase(self, current_node: str) -> SimulationPhase:
        mapping = {
            "orchestration": SimulationPhase.PARALLEL_AGENTS,
            "parallel_agents": SimulationPhase.DEBATE,
            "debate": SimulationPhase.TIMELINE,
            "timeline": SimulationPhase.EVENTS,
            "events": SimulationPhase.CRITIQUE,
            "critic": SimulationPhase.FUTURE_SELF,
            "future_self": SimulationPhase.SYNTHESIS,
            "synthesis": SimulationPhase.COMPLETE,
        }
        return mapping.get(current_node, SimulationPhase.COMPLETE)

    def execute(self, state: SimulationState) -> SimulationState:
        logger.info("[Graph] Starting simulation graph execution")
        self._notify_observers("start", state)

        ordered_nodes = [
            "orchestration",
            "parallel_agents",
            "debate",
            "timeline",
            "events",
            "critic",
            "future_self",
            "synthesis",
        ]

        current_state = state
        for node_name in ordered_nodes:
            if current_state.phase == SimulationPhase.FAILED:
                logger.warning("[Graph] Halting due to failed state at %s", node_name)
                break

            node_def = self.nodes.get(node_name)
            if not node_def:
                logger.error("[Graph] Node '%s' not found", node_name)
                continue

            self._notify_observers(f"before_{node_name}", current_state)
            current_state = self._execute_node(node_def, current_state)
            self._notify_observers(f"after_{node_name}", current_state)

        if current_state.phase == SimulationPhase.COMPLETE:
            logger.info("[Graph] Simulation completed successfully in %.0fms", current_state.latency_ms)
        else:
            logger.error("[Graph] Simulation ended in phase: %s", current_state.phase)

        self._notify_observers("complete", current_state)
        return current_state


def build_default_graph() -> SimulationGraph:
    graph = SimulationGraph()

    graph.add_node("orchestration", orchestration_node, retries=1, timeout_ms=30000)
    graph.add_node("parallel_agents", run_all_parallel_agents, retries=1, timeout_ms=120000)
    graph.add_node("debate", debate_node, retries=1, timeout_ms=60000)
    graph.add_node("timeline", timeline_node, retries=1, timeout_ms=120000)
    graph.add_node("events", event_engine_node, retries=1, timeout_ms=60000)
    graph.add_node("critic", critic_node, retries=1, timeout_ms=60000)
    graph.add_node("future_self", future_self_node, retries=1, timeout_ms=60000)
    graph.add_node("synthesis", synthesis_node, retries=2, timeout_ms=90000)

    graph.add_edge("orchestration", "parallel_agents")
    graph.add_edge("parallel_agents", "debate")
    graph.add_edge("debate", "timeline")
    graph.add_edge("timeline", "events")
    graph.add_edge("events", "critic")
    graph.add_edge("critic", "future_self")
    graph.add_edge("future_self", "synthesis")

    return graph


def create_simulation(decision: str, context: dict) -> SimulationState:
    from graph.state import EconomicState
    state = SimulationState(
        decision=decision,
        context=context,
        economic=EconomicState(),
    )
    return state
