"""
Tests: graph/agents/*.py — all 6 specialist agents + LLMAgent base class.

Run: python3 -m pytest tests/test_graph_agents.py -v
Or:  python3 tests/test_graph_agents.py
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


class TestLLMAgent(unittest.TestCase):
    """LLMAgent base class — JSON repair, prompt building, run"""

    def setUp(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            from graph.agents.llm_agent import LLMAgent
            self.agent = LLMAgent("test_agent", "economic.txt", temperature=0.3)

    def test_build_prompt_substitutes_vars(self):
        prompt = self.agent.build_prompt(
            decision="test decision",
            context='{"key": "value"}',
            gdp_growth="6.5",
            memory_context="No context",
        )
        self.assertIn("test decision", prompt)
        self.assertIn("6.5", prompt)

    def test_load_prompt_returns_string(self):
        prompt = self.agent.load_prompt()
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)

    def test_run_structured_valid_json(self):
        with patch.object(self.agent, "run", return_value='{"ok": true}'):
            result = self.agent.run_structured("test prompt")
            self.assertEqual(result, {"ok": True})

    def test_run_structured_repairs_markdown_json(self):
        with patch.object(self.agent, "run", return_value='```json\n{"ok": true}\n```'):
            result = self.agent.run_structured("test prompt")
            self.assertEqual(result, {"ok": True})

    def test_run_structured_repairs_truncated_json(self):
        with patch.object(self.agent, "run", return_value='some text {"ok": true} trailing'):
            result = self.agent.run_structured("test prompt")
            self.assertEqual(result, {"ok": True})

    def test_run_structured_raises_on_empty(self):
        with patch.object(self.agent, "run", return_value=""):
            with self.assertRaises(ValueError):
                self.agent.run_structured("test prompt")

    def test_run_structured_raises_on_bad_json(self):
        with patch.object(self.agent, "run", return_value="not json at all"):
            with self.assertRaises(ValueError):
                self.agent.run_structured("test prompt")

    def test_metrics_initializes(self):
        metrics = self.agent.metrics()
        self.assertEqual(metrics["calls"], 0)
        self.assertEqual(metrics["cache_hits"], 0)

    @patch("graph.agents.llm_agent.get_quota_manager")
    @patch("graph.agents.llm_agent.get_cache")
    @patch("graph.agents.llm_agent.call_llm")
    def test_run_calls_llm(self, mock_call_llm, mock_get_cache, mock_get_qm):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_get_cache.return_value = mock_cache
        mock_qm = MagicMock()
        mock_get_qm.return_value = mock_qm
        mock_call_llm.return_value = '{"ok": true}'
        result = self.agent.run("test")
        self.assertEqual(result, '{"ok": true}')
        mock_call_llm.assert_called_once()
        self.assertEqual(self.agent._metrics["calls"], 1)

    @patch("graph.agents.llm_agent.get_quota_manager")
    @patch("graph.agents.llm_agent.get_cache")
    def test_run_uses_cache(self, mock_get_cache, mock_get_qm):
        mock_cache = MagicMock()
        mock_cache.get.return_value = '{"cached": true}'
        mock_get_cache.return_value = mock_cache
        mock_get_qm.return_value = MagicMock()
        result = self.agent.run("test", use_cache=True)
        self.assertEqual(result, '{"cached": true}')
        self.assertEqual(self.agent._metrics["cache_hits"], 1)


class TestEconomicAgentDeterministic(unittest.TestCase):
    """EconomicAgent._deterministic with type safety"""

    def setUp(self):
        self.qm_patcher = patch("graph.agents.economic.get_quota_manager")
        self.mock_qm = self.qm_patcher.start()
        self.mock_qm.should_use_llm.return_value = False
        self.mock_qm.mode = "deterministic"

    def tearDown(self):
        self.qm_patcher.stop()

    def test_analyze_returns_dict_with_expected_keys(self):
        from graph.agents.economic import EconomicAgent
        agent = EconomicAgent()
        result = agent.analyze("test decision", {"location": "Bangalore"}, {"gdp_growth": 6.49})
        self.assertIn("gdp_forecast", result)
        self.assertIn("salary_growth_forecast", result)
        self.assertIn("inflation_forecast", result)
        self.assertIn("confidence", result)

    def test_analyze_non_dict_context(self):
        from graph.agents.economic import EconomicAgent
        agent = EconomicAgent()
        result = agent.analyze("test", "bad_context", {})
        self.assertIn("gdp_forecast", result)

    def test_analyze_non_dict_economic_data(self):
        from graph.agents.economic import EconomicAgent
        agent = EconomicAgent()
        result = agent.analyze("test", {}, "bad_economic")
        self.assertIn("gdp_forecast", result)

    def test_deterministic_non_dict_data(self):
        from graph.agents.economic import EconomicAgent
        agent = EconomicAgent()
        result = agent._deterministic({}, None)
        self.assertIn("gdp_forecast", result)


class TestCareerAgentDeterministic(unittest.TestCase):
    """CareerAgent._deterministic"""

    def setUp(self):
        self.qm_patcher = patch("graph.agents.career.get_quota_manager")
        self.mock_qm = self.qm_patcher.start()
        self.mock_qm.should_use_llm.return_value = False

    def tearDown(self):
        self.qm_patcher.stop()

    def test_analyze_returns_career_fields(self):
        from graph.agents.career import CareerAgent
        agent = CareerAgent()
        result = agent.analyze("test", {"location": "Bangalore"}, {"industry_health": 78})
        self.assertIn("skill_growth_forecast", result)
        self.assertIn("employability_forecast", result)
        self.assertIn("promotion_timeline", result)
        self.assertIn("confidence", result)
        self.assertEqual(len(result["skill_growth_forecast"]), 5)

    def test_analyze_non_dict_context(self):
        from graph.agents.career import CareerAgent
        agent = CareerAgent()
        result = agent.analyze("test", "bad", {})
        self.assertIn("skill_growth_forecast", result)

    def test_analyze_non_dict_economic(self):
        from graph.agents.career import CareerAgent
        agent = CareerAgent()
        result = agent.analyze("test", {}, "bad")
        self.assertIn("skill_growth_forecast", result)


class TestFinancialAgentDeterministic(unittest.TestCase):
    """FinancialAgent._deterministic"""

    def setUp(self):
        self.qm_patcher = patch("graph.agents.financial.get_quota_manager")
        self.mock_qm = self.qm_patcher.start()
        self.mock_qm.should_use_llm.return_value = False

    def tearDown(self):
        self.qm_patcher.stop()

    def test_analyze_returns_financial_fields(self):
        from graph.agents.financial import FinancialAgent
        agent = FinancialAgent()
        result = agent.analyze("test", {"financial_condition": "stable"}, {"interest_rate": 6.5})
        self.assertIn("net_worth_forecast", result)
        self.assertIn("financial_risk_score", result)
        self.assertIn("key_insights", result)
        self.assertIn("confidence", result)
        self.assertEqual(len(result["net_worth_forecast"]), 5)

    def test_analyze_non_dict_context(self):
        from graph.agents.financial import FinancialAgent
        agent = FinancialAgent()
        result = agent.analyze("test", "bad", {})
        self.assertIn("net_worth_forecast", result)


class TestHealthAgentDeterministic(unittest.TestCase):
    """HealthAgent._deterministic"""

    def setUp(self):
        self.qm_patcher = patch("graph.agents.health.get_quota_manager")
        self.mock_qm = self.qm_patcher.start()
        self.mock_qm.should_use_llm.return_value = False

    def tearDown(self):
        self.qm_patcher.stop()

    def test_analyze_returns_health_fields(self):
        from graph.agents.health import HealthAgent
        agent = HealthAgent()
        result = agent.analyze("test", {"work_hours": 45, "location": "Bangalore"}, {})
        self.assertIn("burnout_risk_forecast", result)
        self.assertIn("stress_trajectory", result)
        self.assertIn("long_term_wellbeing_score", result)
        self.assertEqual(len(result["stress_trajectory"]), 5)

    def test_analyze_non_dict_economic(self):
        from graph.agents.health import HealthAgent
        agent = HealthAgent()
        result = agent.analyze("test", {}, "bad")
        self.assertIn("burnout_risk_forecast", result)

    def test_deterministic_returns_recommendations(self):
        from graph.agents.health import HealthAgent
        agent = HealthAgent()
        result = agent._deterministic({"work_hours": 40, "location": "Pune"}, {}, {})
        self.assertIn("recommendations", result)
        self.assertGreater(len(result["recommendations"]), 0)


class TestRelationshipAgentDeterministic(unittest.TestCase):
    """RelationshipAgent._deterministic"""

    def setUp(self):
        self.qm_patcher = patch("graph.agents.relationship.get_quota_manager")
        self.mock_qm = self.qm_patcher.start()
        self.mock_qm.should_use_llm.return_value = False

    def tearDown(self):
        self.qm_patcher.stop()

    def test_analyze_returns_relationship_fields(self):
        from graph.agents.relationship import RelationshipAgent
        agent = RelationshipAgent()
        result = agent.analyze("test", {"location": "Bangalore"}, {})
        self.assertIn("family_stability_forecast", result)
        self.assertIn("social_connection_forecast", result)
        self.assertIn("relationship_wealth_index", result)
        self.assertEqual(len(result["family_stability_forecast"]), 5)

    def test_analyze_non_dict_context(self):
        from graph.agents.relationship import RelationshipAgent
        agent = RelationshipAgent()
        result = agent.analyze("test", "bad", {})
        self.assertIn("family_stability_forecast", result)

    def test_analyze_non_dict_economic(self):
        from graph.agents.relationship import RelationshipAgent
        agent = RelationshipAgent()
        result = agent.analyze("test", {}, "bad")
        self.assertIn("family_stability_forecast", result)


class TestOpportunityAgentDeterministic(unittest.TestCase):
    """OpportunityAgent._deterministic — was the source of 'str has no .get' crash"""

    def setUp(self):
        self.qm_patcher = patch("graph.agents.opportunity.get_quota_manager")
        self.mock_qm = self.qm_patcher.start()
        self.mock_qm.should_use_llm.return_value = False

    def tearDown(self):
        self.qm_patcher.stop()

    def test_analyze_returns_opportunity_fields(self):
        from graph.agents.opportunity import OpportunityAgent
        agent = OpportunityAgent()
        result = agent.analyze("test", {"industry": "technology", "location": "Bangalore"}, {"industry_health": 78})
        self.assertIn("career_opportunities", result)
        self.assertIn("opportunity_score_forecast", result)
        self.assertIn("confidence", result)

    def test_analyze_non_dict_context(self):
        from graph.agents.opportunity import OpportunityAgent
        agent = OpportunityAgent()
        result = agent.analyze("test", "bad_context", {})
        self.assertIn("career_opportunities", result)
        self.assertIsInstance(result["career_opportunities"], list)

    def test_analyze_non_dict_economic_data(self):
        from graph.agents.opportunity import OpportunityAgent
        agent = OpportunityAgent()
        result = agent.analyze("test", {}, "string_instead_of_dict")
        self.assertIn("career_opportunities", result)

    def test_analyze_with_none_economic_does_not_crash(self):
        from graph.agents.opportunity import OpportunityAgent
        agent = OpportunityAgent()
        result = agent.analyze("test", {}, None)
        self.assertIn("career_opportunities", result)


class TestAgentLLMFallback(unittest.TestCase):
    """All agents gracefully fall back to deterministic when LLM fails"""

    def setUp(self):
        self.qm_patcher = patch("graph.agents.economic.get_quota_manager")
        self.mock_qm = self.qm_patcher.start()
        self.mock_qm.should_use_llm.return_value = True

    def tearDown(self):
        self.qm_patcher.stop()

    def test_economic_falls_back_on_llm_failure(self):
        from graph.agents.economic import EconomicAgent
        agent = EconomicAgent()
        with patch.object(agent, "run_structured", side_effect=Exception("LLM down")):
            result = agent.analyze("test", {"location": "Bangalore"}, {"gdp_growth": 6.49})
            self.assertIn("gdp_forecast", result)
            self.assertIn("salary_growth_forecast", result)

    def test_career_falls_back_on_llm_failure(self):
        from graph.agents.career import CareerAgent
        agent = CareerAgent()
        with patch.object(agent, "run_structured", side_effect=Exception("LLM down")):
            result = agent.analyze("test", {"location": "Bangalore"}, {"industry_health": 78})
            self.assertIn("skill_growth_forecast", result)

    def test_financial_falls_back_on_llm_failure(self):
        from graph.agents.financial import FinancialAgent
        agent = FinancialAgent()
        with patch.object(agent, "run_structured", side_effect=Exception("LLM down")):
            result = agent.analyze("test", {"financial_condition": "stable"}, {"interest_rate": 6.5})
            self.assertIn("net_worth_forecast", result)

    def test_health_falls_back_on_llm_failure(self):
        from graph.agents.health import HealthAgent
        agent = HealthAgent()
        with patch.object(agent, "run_structured", side_effect=Exception("LLM down")):
            result = agent.analyze("test", {"work_hours": 45}, {})
            self.assertIn("burnout_risk_forecast", result)

    def test_relationship_falls_back_on_llm_failure(self):
        from graph.agents.relationship import RelationshipAgent
        agent = RelationshipAgent()
        with patch.object(agent, "run_structured", side_effect=Exception("LLM down")):
            result = agent.analyze("test", {"location": "Bangalore"}, {})
            self.assertIn("family_stability_forecast", result)

    def test_opportunity_falls_back_on_llm_failure(self):
        from graph.agents.opportunity import OpportunityAgent
        agent = OpportunityAgent()
        with patch.object(agent, "run_structured", side_effect=Exception("LLM down")):
            result = agent.analyze("test", {"industry": "tech"}, {"industry_health": 78})
            self.assertIn("career_opportunities", result)


if __name__ == "__main__":
    unittest.main()
