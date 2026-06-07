"""
Tests: graph/workflows/monte_carlo.py — 10K-iteration simulation with probability distributions.
"""
import os
import sys
import time
import types as pytypes
import unittest
from unittest.mock import MagicMock, patch

sys.modules["google.genai"] = pytypes.ModuleType("google.genai")
sys.modules["google.genai.types"] = pytypes.ModuleType("google.genai.types")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
logging.disable(logging.CRITICAL)

LIVE_DATA = {
    "gdp_growth": 6.49, "inflation_cpi": 4.95, "unemployment_rate": 4.22,
    "interest_rate": 6.5, "salary_growth_pct": 7.5, "salary_lpa": 9.5,
    "salary_range_lpa": [6, 15], "industry_growth_rate": 8.0,
    "industry_health": 78.0, "automation_risk": 15.0,
    "cost_of_living_index": 1.2,
    "sources": {"worldbank": {"available": True}, "ambitionbox": {"available": True}},
    "errors": {},
    "gdp_available": True, "salary_available": True,
    "industry_available": True, "cost_of_living_available": True,
    "all_sources_available": True,
    "gdp_is_historical": True, "gdp_data_year": "2023",
}


class TestMonteCarloRun(unittest.TestCase):
    """run_monte_carlo — end-to-end"""

    def setUp(self):
        self.decision = "Should I switch to AI engineering?"
        self.context = {"work_hours": 45, "location": "Bangalore", "risk_tolerance": "medium"}

    @patch("graph.workflows.monte_carlo.collect_economic_data", return_value=LIVE_DATA)
    def test_returns_dict_with_expected_keys(self, mock_data):
        from graph.workflows.monte_carlo import run_monte_carlo
        result = run_monte_carlo(self.decision, self.context, iterations=50, parallel=False)
        self.assertIn("success_probability", result)
        self.assertIn("failure_probability", result)
        self.assertIn("neutral_probability", result)
        self.assertIn("regret_probability", result)
        self.assertIn("iterations_run", result)
        self.assertIn("iterations_requested", result)
        self.assertIn("income_distribution", result)
        self.assertIn("happiness_distribution", result)
        self.assertIn("stress_distribution", result)
        self.assertIn("timeline_comparison", result)
        self.assertIn("data_sources", result)

    @patch("graph.workflows.monte_carlo.collect_economic_data", return_value=LIVE_DATA)
    def test_probabilities_sum_to_approx_1(self, mock_data):
        from graph.workflows.monte_carlo import run_monte_carlo
        result = run_monte_carlo(self.decision, self.context, iterations=100, parallel=False)
        total = result["success_probability"] + result["failure_probability"] + result["neutral_probability"]
        self.assertAlmostEqual(total, 1.0, places=1)

    @patch("graph.workflows.monte_carlo.collect_economic_data", return_value=LIVE_DATA)
    def test_probabilities_are_decimals_between_0_and_1(self, mock_data):
        from graph.workflows.monte_carlo import run_monte_carlo
        result = run_monte_carlo(self.decision, self.context, iterations=100, parallel=False)
        for key in ["success_probability", "failure_probability", "neutral_probability", "regret_probability"]:
            v = result[key]
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    @patch("graph.workflows.monte_carlo.collect_economic_data", return_value=LIVE_DATA)
    def test_iterations_run_matches_requested(self, mock_data):
        from graph.workflows.monte_carlo import run_monte_carlo
        result = run_monte_carlo(self.decision, self.context, iterations=50, parallel=False)
        self.assertEqual(result["iterations_run"], 50)

    @patch("graph.workflows.monte_carlo.collect_economic_data", return_value=LIVE_DATA)
    def test_income_distribution_has_min_max_median_mean(self, mock_data):
        from graph.workflows.monte_carlo import run_monte_carlo
        result = run_monte_carlo(self.decision, self.context, iterations=50, parallel=False)
        dist = result["income_distribution"]
        self.assertIn("min", dist)
        self.assertIn("max", dist)
        self.assertIn("median", dist)
        self.assertIn("mean", dist)
        self.assertLessEqual(dist["min"], dist["max"])

    @patch("graph.workflows.monte_carlo.collect_economic_data", return_value=LIVE_DATA)
    def test_happiness_distribution_has_upper_and_lower(self, mock_data):
        from graph.workflows.monte_carlo import run_monte_carlo
        result = run_monte_carlo(self.decision, self.context, iterations=50, parallel=False)
        dist = result["happiness_distribution"]
        self.assertIn("lower", dist)
        self.assertIn("upper", dist)
        self.assertIn("median", dist)

    @patch("graph.workflows.monte_carlo.collect_economic_data", return_value=LIVE_DATA)
    def test_timeline_comparison_has_all_archetypes(self, mock_data):
        from graph.workflows.monte_carlo import run_monte_carlo
        result = run_monte_carlo(self.decision, self.context, iterations=50, parallel=False)
        tc = result["timeline_comparison"]
        self.assertIn("Timeline A", tc)
        self.assertIn("Timeline B", tc)
        self.assertIn("Timeline C", tc)

    @patch("graph.workflows.monte_carlo.collect_economic_data", return_value=LIVE_DATA)
    def test_timeline_comparison_nodes_have_mean_std(self, mock_data):
        from graph.workflows.monte_carlo import run_monte_carlo
        result = run_monte_carlo(self.decision, self.context, iterations=50, parallel=False)
        tl_b = result["timeline_comparison"]["Timeline B"]
        for node in ["income", "career_growth", "stress", "health", "relationships", "happiness", "opportunity"]:
            self.assertIn(node, tl_b)
            self.assertIn("mean", tl_b[node])
            self.assertIn("std", tl_b[node])

    @patch("graph.workflows.monte_carlo.collect_economic_data", return_value=LIVE_DATA)
    def test_data_sources_has_summary(self, mock_data):
        from graph.workflows.monte_carlo import run_monte_carlo
        result = run_monte_carlo(self.decision, self.context, iterations=50, parallel=False)
        ds = result["data_sources"]
        self.assertIn("_summary", ds)
        self.assertIn("data_quality_pct", ds["_summary"])


class TestMonteCarloEmpty(unittest.TestCase):
    """Edge case: no results"""

    def test_analyze_empty_results_returns_defaults(self):
        from graph.workflows.monte_carlo import _analyze_results
        result = _analyze_results([], 100)
        self.assertEqual(result["success_probability"], 0.0)
        self.assertEqual(result["failure_probability"], 0.0)
        self.assertEqual(result["neutral_probability"], 1.0)
        self.assertEqual(result["regret_probability"], 0.0)
        self.assertEqual(result["iterations_run"], 0)


class TestSingleIteration(unittest.TestCase):
    """_run_single_iteration"""

    def setUp(self):
        self.decision = "test"
        self.context = {"work_hours": 45, "risk_tolerance": "medium"}

    def test_returns_seed_economic_scores_timeline_details(self):
        from graph.workflows.monte_carlo import _run_single_iteration
        result = _run_single_iteration(self.decision, self.context, LIVE_DATA, seed=42)
        self.assertIn("seed", result)
        self.assertEqual(result["seed"], 42)
        self.assertIn("economic", result)
        self.assertIn("scores", result)
        self.assertIn("timeline_details", result)

    def test_all_3_timelines_have_all_7_nodes(self):
        from graph.workflows.monte_carlo import _run_single_iteration
        result = _run_single_iteration(self.decision, self.context, LIVE_DATA, seed=42)
        for tl in ["Timeline A", "Timeline B", "Timeline C"]:
            self.assertIn(tl, result["scores"])
            for node in ["income", "career_growth", "stress", "health", "relationships", "happiness", "opportunity"]:
                self.assertIn(node, result["scores"][tl])

    def test_5_years_in_timeline_details(self):
        from graph.workflows.monte_carlo import _run_single_iteration
        result = _run_single_iteration(self.decision, self.context, LIVE_DATA, seed=42)
        for tl in ["Timeline A", "Timeline B", "Timeline C"]:
            detail = result["timeline_details"][tl]
            for y in ["Year1", "Year3", "Year5", "Year7", "Year10"]:
                self.assertIn(y, detail)

    def test_max_income_and_avg_income(self):
        from graph.workflows.monte_carlo import _run_single_iteration
        result = _run_single_iteration(self.decision, self.context, LIVE_DATA, seed=42)
        self.assertIn("max_income", result)
        self.assertIn("avg_income", result)
        self.assertGreaterEqual(result["max_income"], result["avg_income"])

    def test_different_seeds_produce_different_results(self):
        from graph.workflows.monte_carlo import _run_single_iteration
        r1 = _run_single_iteration(self.decision, self.context, LIVE_DATA, seed=1)
        r2 = _run_single_iteration(self.decision, self.context, LIVE_DATA, seed=999)
        self.assertNotEqual(r1["max_income"], r2["max_income"])

    def test_includes_avg_stress(self):
        from graph.workflows.monte_carlo import _run_single_iteration
        result = _run_single_iteration(self.decision, self.context, LIVE_DATA, seed=42)
        self.assertIn("avg_stress", result)


class TestMonteCarloParallel(unittest.TestCase):
    """run_monte_carlo with parallel=True"""

    @patch("graph.workflows.monte_carlo.collect_economic_data", return_value=LIVE_DATA)
    def test_parallel_returns_same_structure(self, mock_data):
        from graph.workflows.monte_carlo import run_monte_carlo
        result = run_monte_carlo("test decision", {"work_hours": 40}, iterations=50, parallel=True)
        self.assertIn("success_probability", result)
        self.assertIn("regret_probability", result)
        self.assertEqual(result["iterations_run"], 50)


class TestMonteCarloScalability(unittest.TestCase):
    """Verify performance characteristics"""

    @patch("graph.workflows.monte_carlo.collect_economic_data", return_value=LIVE_DATA)
    def test_100_iterations_fast(self, mock_data):
        from graph.workflows.monte_carlo import run_monte_carlo
        start = time.time()
        run_monte_carlo("test", {"work_hours": 40}, iterations=100, parallel=False)
        elapsed = time.time() - start
        self.assertLess(elapsed, 10, "100 iterations should complete in <10s")


if __name__ == "__main__":
    unittest.main()
