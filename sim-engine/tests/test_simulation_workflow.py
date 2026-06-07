"""
Tests: graph/workflows/simulation.py + graph/nodes/parallel_agents.py.

Run: python3 -m pytest tests/test_simulation_workflow.py -v
Or:  python3 tests/test_simulation_workflow.py
"""
import json
import os
import sys
import types as pytypes
import unittest
from unittest.mock import MagicMock, patch

# Mock google.genai before imports
import google as google_module
_genai_pkg = pytypes.ModuleType("google.genai")
_genai_pkg.Client = MagicMock()
_genai_pkg.types = pytypes.ModuleType("google.genai.types")
_genai_pkg.protos = pytypes.ModuleType("google.genai.protos")
sys.modules["google.genai"] = _genai_pkg
sys.modules["google.genai.types"] = _genai_pkg.types
sys.modules["google.genai.protos"] = _genai_pkg.protos
google_module.genai = _genai_pkg

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
logging.disable(logging.CRITICAL)
from graph.state import SimulationState, SimulationPhase, AgentOutput


class TestCreateSimulation(unittest.TestCase):
    """create_simulation"""

    def test_returns_state_with_decision_and_context(self):
        from graph.builder import create_simulation
        state = create_simulation("test decision", {"key": "value"})
        self.assertIsInstance(state, SimulationState)
        self.assertEqual(state.decision, "test decision")
        self.assertEqual(state.context, {"key": "value"})
        self.assertEqual(state.phase, SimulationPhase.ORCHESTRATION)

    def test_economic_state_initialized(self):
        from graph.builder import create_simulation
        state = create_simulation("test", {})
        self.assertIsNotNone(state.economic)
        self.assertIsNone(state.economic.gdp_growth)
        self.assertFalse(state.economic.data_available)


class TestStateToResult(unittest.TestCase):
    """_state_to_result"""

    def setUp(self):
        self.state = SimulationState(decision="test", context={})
        self.state.agent_outputs["economic"] = AgentOutput(
            agent_name="economic", output={"forecast": 123}, confidence=0.8,
            latency_ms=50, model_used="llm",
        )
        self.state.phase = SimulationPhase.COMPLETE

    def test_agent_outputs_flattened(self):
        from graph.workflows.simulation import _state_to_result
        result = _state_to_result(self.state)
        eco = result["agent_outputs"]["economic"]
        self.assertEqual(eco["forecast"], 123)
        self.assertEqual(eco["confidence"], 0.8)
        self.assertEqual(eco["agent_name"], "economic")

    def test_includes_metadata_fields(self):
        from graph.workflows.simulation import _state_to_result
        result = _state_to_result(self.state)
        self.assertIn("simulation_id", result)
        self.assertIn("decision", result)
        self.assertIn("phase", result)
        self.assertIn("agent_outputs", result)
        self.assertIn("economic", result)


class TestParallelAgentNodes(unittest.TestCase):
    """Each agent node handles errors gracefully"""

    def setUp(self):
        self.state = SimulationState(
            decision="test decision",
            context={"location": "Bangalore", "_computed": {}},
        )
        self.qm_patchers = {}
        for name in ["economic", "career", "financial", "health", "relationship", "opportunity"]:
            p = patch(f"graph.nodes.parallel_agents.{name.capitalize()}Agent")
            self.qm_patchers[name] = p.start()
        self.env_patcher = patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
        self.env_patcher.start()

    def tearDown(self):
        for p in self.qm_patchers.values():
            p.stop()
        self.env_patcher.stop()

    def test_run_economic_agent_sets_output(self):
        from graph.nodes.parallel_agents import run_economic_agent
        with patch("graph.nodes.parallel_agents.extract_economic_data", return_value={}):
            result = run_economic_agent(self.state)
        self.assertIn("economic", result.agent_outputs)

    def test_run_economic_agent_on_error_sets_fallback(self):
        from graph.nodes.parallel_agents import run_economic_agent
        with patch("graph.nodes.parallel_agents.EconomicAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.analyze.side_effect = Exception("fail")
            result = run_economic_agent(self.state)
        eco = result.agent_outputs["economic"]
        self.assertEqual(eco.output, {})
        self.assertEqual(eco.confidence, 0.0)
        self.assertEqual(eco.model_used, "fallback")
        self.assertIn("fail", eco.error)

    def test_run_career_agent_on_error_sets_fallback(self):
        from graph.nodes.parallel_agents import run_career_agent
        with patch("graph.nodes.parallel_agents.CareerAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.analyze.side_effect = Exception("career fail")
            result = run_career_agent(self.state)
        career = result.agent_outputs["career"]
        self.assertEqual(career.model_used, "fallback")

    def test_run_financial_agent_on_error_sets_fallback(self):
        from graph.nodes.parallel_agents import run_financial_agent
        with patch("graph.nodes.parallel_agents.FinancialAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.analyze.side_effect = Exception("fin fail")
            result = run_financial_agent(self.state)
        self.assertEqual(result.agent_outputs["financial"].model_used, "fallback")

    def test_run_health_agent_on_error_sets_fallback(self):
        from graph.nodes.parallel_agents import run_health_agent
        with patch("graph.nodes.parallel_agents.HealthAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.analyze.side_effect = Exception("health fail")
            result = run_health_agent(self.state)
        self.assertEqual(result.agent_outputs["health"].model_used, "fallback")

    def test_run_relationship_agent_on_error_sets_fallback(self):
        from graph.nodes.parallel_agents import run_relationship_agent
        with patch("graph.nodes.parallel_agents.RelationshipAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.analyze.side_effect = Exception("rel fail")
            result = run_relationship_agent(self.state)
        self.assertEqual(result.agent_outputs["relationship"].model_used, "fallback")

    def test_run_opportunity_agent_on_error_sets_fallback(self):
        from graph.nodes.parallel_agents import run_opportunity_agent
        with patch("graph.nodes.parallel_agents.OpportunityAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.analyze.side_effect = Exception("opp fail")
            result = run_opportunity_agent(self.state)
        self.assertEqual(result.agent_outputs["opportunity"].model_used, "fallback")

    def test_run_all_parallel_updates_phase(self):
        from graph.nodes.parallel_agents import run_all_parallel_agents
        result = run_all_parallel_agents(self.state)
        self.assertEqual(result.phase, SimulationPhase.DEBATE)

    def test_get_memory_context_string(self):
        from graph.nodes.parallel_agents import _get_memory_context
        self.state.memory_context = "direct string"
        result = _get_memory_context(self.state)
        self.assertEqual(result, "direct string")

    def test_get_memory_context_dict(self):
        from graph.nodes.parallel_agents import _get_memory_context
        self.state.memory_context = {"key": "value"}
        result = _get_memory_context(self.state)
        self.assertIn("key", result)

    def test_get_memory_context_none(self):
        from graph.nodes.parallel_agents import _get_memory_context
        result = _get_memory_context(self.state)
        self.assertEqual(result, "No prior context available.")


class TestSimulationGraph(unittest.TestCase):
    """SimulationGraph builder and execution"""

    def setUp(self):
        self.state = SimulationState(decision="test", context={})

    def test_build_graph_has_all_nodes(self):
        from graph.builder import build_default_graph
        graph = build_default_graph()
        expected = ["orchestration", "parallel_agents", "debate", "timeline",
                     "events", "critic", "future_self", "synthesis"]
        for name in expected:
            self.assertIn(name, graph.nodes)

    def test_execute_on_failed_state_halts(self):
        from graph.builder import SimulationGraph
        graph = SimulationGraph()
        self.state.phase = SimulationPhase.FAILED
        result = graph.execute(self.state)
        self.assertEqual(result.phase, SimulationPhase.FAILED)

    @patch("graph.builder.orchestration_node")
    def test_execute_runs_through_pipeline(self, mock_orch):
        from graph.builder import build_default_graph
        mock_orch.return_value = self.state
        graph = build_default_graph()

        class FakeNode:
            def __init__(self, name):
                self.name = name
                self.fn = lambda s: s
                self.retries = 1
                self.timeout_ms = 1000

        for n in ["debate", "timeline", "events", "critic", "future_self", "synthesis"]:
            graph.nodes[n] = FakeNode(n)
        # Override parallel_agents similarly
        graph.nodes["parallel_agents"] = FakeNode("parallel_agents")

        result = graph.execute(self.state)
        self.assertIn(result.phase, [SimulationPhase.COMPLETE, SimulationPhase.PARALLEL_AGENTS])


class TestRunSimulation(unittest.TestCase):
    """run_simulation (integration-level, mocked)"""

    @patch("graph.workflows.simulation.build_default_graph")
    def test_run_simulation_returns_dict(self, mock_build_graph):
        from graph.workflows.simulation import run_simulation
        mock_graph = MagicMock()
        final_state = SimulationState(decision="test", context={})
        final_state.phase = SimulationPhase.COMPLETE
        mock_graph.execute.return_value = final_state
        mock_build_graph.return_value = mock_graph

        result = run_simulation("test decision", {"key": "value"})
        self.assertIsInstance(result, dict)
        self.assertIn("simulation_id", result)
        self.assertIn("decision", result)

    @patch("graph.workflows.simulation.build_default_graph")
    def test_run_simulation_applies_economic_override(self, mock_build_graph):
        from graph.workflows.simulation import run_simulation
        mock_graph = MagicMock()
        final_state = SimulationState(decision="test", context={})
        final_state.phase = SimulationPhase.COMPLETE
        mock_graph.execute.return_value = final_state
        mock_build_graph.return_value = mock_graph

        result = run_simulation("test", {}, economic_override={"gdp_growth": 8.0})
        self.assertIn("decision", result)


if __name__ == "__main__":
    unittest.main()
