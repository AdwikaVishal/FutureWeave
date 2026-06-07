"""
Tests: deterministic_formulas.py — all 23 formula functions.

Run: python3 -m pytest tests/test_deterministic_formulas.py -v
Or:  python3 tests/test_deterministic_formulas.py
"""
import os
import sys
import unittest
import types as pytypes
from unittest.mock import MagicMock, patch

sys.modules["google.genai"] = pytypes.ModuleType("google.genai")
sys.modules["google.genai.types"] = pytypes.ModuleType("google.genai.types")
sys.modules["google.genai.protos"] = pytypes.ModuleType("google.genai.protos")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
logging.disable(logging.CRITICAL)


class TestClamp(unittest.TestCase):
    """_clamp helper"""

    def test_clamps_below_min(self):
        from deterministic_formulas import _clamp
        self.assertEqual(_clamp(-5, 0, 100), 0)

    def test_clamps_above_max(self):
        from deterministic_formulas import _clamp
        self.assertEqual(_clamp(150, 0, 100), 100)

    def test_passes_through(self):
        from deterministic_formulas import _clamp
        self.assertEqual(_clamp(50, 0, 100), 50)


class TestGrowthDecayCurves(unittest.TestCase):
    """_growth_curve and _decay_curve"""

    def test_growth_curve_starts_at_base(self):
        from deterministic_formulas import _growth_curve
        val = _growth_curve(30, 0.25, 1, 95)
        self.assertGreater(val, 30)
        self.assertLessEqual(val, 95)

    def test_growth_curve_approaches_cap(self):
        from deterministic_formulas import _growth_curve
        val = _growth_curve(30, 0.5, 10, 95)
        self.assertAlmostEqual(val, 95, delta=5)

    def test_decay_curve_starts_high(self):
        from deterministic_formulas import _decay_curve
        val = _decay_curve(80, 0.2, 1, 20)
        self.assertLess(val, 80)
        self.assertGreaterEqual(val, 20)

    def test_decay_curve_approaches_floor(self):
        from deterministic_formulas import _decay_curve
        val = _decay_curve(80, 0.5, 10, 20)
        self.assertAlmostEqual(val, 20, delta=5)

    def test_year_multiplier(self):
        from deterministic_formulas import _year_multiplier
        self.assertAlmostEqual(_year_multiplier("Year1", 1.0), 1.0)
        self.assertGreater(_year_multiplier("Year5", 1.0), 1.0)


class TestCareerFormulas(unittest.TestCase):
    """compute_skill_growth, compute_employability, compute_promotion_timeline, compute_leadership"""

    def setUp(self):
        self.profile = {}
        self.context = {"location": "Bangalore", "skills": ["Python"], "work_hours": 45}
        self.economic = {"industry_health": 78, "automation_risk": 15, "unemployment_rate": 4.22}

    def test_skill_growth_returns_year_and_score(self):
        from deterministic_formulas import compute_skill_growth
        result = compute_skill_growth(self.profile, self.context, self.economic, "Year1")
        self.assertIn("year", result)
        self.assertIn("score", result)
        self.assertIn("narrative", result)
        self.assertEqual(result["year"], "Year1")
        self.assertGreaterEqual(result["score"], 0)

    def test_skill_growth_no_skills_context(self):
        from deterministic_formulas import compute_skill_growth
        ctx = {"location": "remote", "work_hours": 40}
        result = compute_skill_growth(self.profile, ctx, self.economic, "Year5")
        self.assertEqual(result["year"], "Year5")

    def test_employability_returns_year_score_narrative(self):
        from deterministic_formulas import compute_employability
        result = compute_employability(self.profile, self.context, self.economic, "Year1")
        self.assertIn("score", result)
        self.assertIn("narrative", result)

    def test_employability_bangalore_bonus(self):
        from deterministic_formulas import compute_employability
        r1 = compute_employability(self.profile, {"location": "Bangalore"}, self.economic, "Year1")
        r2 = compute_employability(self.profile, {"location": "SmallTown"}, self.economic, "Year1")
        self.assertGreaterEqual(r1["score"], r2["score"])

    def test_promotion_timeline_returns_list(self):
        from deterministic_formulas import compute_promotion_timeline
        result = compute_promotion_timeline(self.profile, self.context, self.economic)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        for entry in result:
            self.assertIn("title", entry)
            self.assertIn("year", entry)

    def test_leadership_returns_dict(self):
        from deterministic_formulas import compute_leadership
        result = compute_leadership(self.profile, self.context, self.economic, "Year3")
        self.assertIn("score", result)
        self.assertIn("narrative", result)


class TestFinancialFormulas(unittest.TestCase):
    """compute_net_worth, compute_financial_risk"""

    def setUp(self):
        self.profile = {}
        self.context = {"risk_tolerance": "medium", "financial_condition": "stable"}
        self.economic = {"interest_rate": 6.5, "inflation_cpi": 4.95, "unemployment_rate": 4.22}

    def test_net_worth_returns_year_amount_narrative(self):
        from deterministic_formulas import compute_net_worth
        result = compute_net_worth(self.profile, self.context, self.economic, "Year1")
        self.assertIn("amount", result)
        self.assertIn("narrative", result)
        self.assertIsInstance(result["amount"], (int, float))
        self.assertGreater(result["amount"], 0)

    def test_net_worth_grows_over_time(self):
        from deterministic_formulas import compute_net_worth
        r1 = compute_net_worth(self.profile, self.context, self.economic, "Year1")
        r5 = compute_net_worth(self.profile, self.context, self.economic, "Year5")
        self.assertGreater(r5["amount"], r1["amount"])

    def test_financial_risk_returns_score_and_narrative(self):
        from deterministic_formulas import compute_financial_risk
        result = compute_financial_risk(self.profile, self.context, self.economic, "Year1")
        self.assertIn("score", result)
        self.assertIn("narrative", result)

    def test_financial_risk_higher_with_debt(self):
        from deterministic_formulas import compute_financial_risk
        r_stable = compute_financial_risk(self.profile, {"financial_condition": "stable"}, self.economic, "Year1")
        r_debt = compute_financial_risk(self.profile, {"financial_condition": "in_debt"}, self.economic, "Year1")
        self.assertGreater(r_debt["score"], r_stable["score"])


class TestHealthFormulas(unittest.TestCase):
    """compute_stress, compute_burnout_risk, compute_work_life_balance, compute_physical_health, compute_mental_health"""

    def setUp(self):
        self.profile = {}
        self.context = {"work_hours": 45, "location": "Bangalore", "risk_tolerance": "medium", "interests": "gym,reading"}
        self.economic = {"inflation_cpi": 4.95, "unemployment_rate": 4.22}

    def test_stress_returns_score_and_narrative(self):
        from deterministic_formulas import compute_stress
        result = compute_stress(self.profile, self.context, self.economic, "Year1")
        self.assertIn("score", result)
        self.assertIn("narrative", result)

    def test_stress_higher_with_long_hours(self):
        from deterministic_formulas import compute_stress
        r1 = compute_stress(self.profile, {"work_hours": 40}, self.economic, "Year1")
        r2 = compute_stress(self.profile, {"work_hours": 70}, self.economic, "Year1")
        self.assertGreaterEqual(r2["score"], r1["score"])

    def test_burnout_risk_returns_risk_and_narrative(self):
        from deterministic_formulas import compute_burnout_risk
        result = compute_burnout_risk(self.profile, self.context, self.economic, "Year3", stress_score=60)
        self.assertIn("risk", result)
        self.assertIn("narrative", result)

    def test_work_life_balance_returns_score(self):
        from deterministic_formulas import compute_work_life_balance
        result = compute_work_life_balance(self.profile, self.context, "Year1")
        self.assertIn("score", result)

    def test_physical_health_returns_score(self):
        from deterministic_formulas import compute_physical_health
        result = compute_physical_health(self.profile, self.context, "Year1", stress_score=50)
        self.assertIn("score", result)

    def test_physical_health_gym_bonus(self):
        from deterministic_formulas import compute_physical_health
        r_active = compute_physical_health(self.profile, {"interests": "gym"}, "Year1", stress_score=50)
        r_no = compute_physical_health(self.profile, {"interests": "reading"}, "Year1", stress_score=50)
        self.assertGreaterEqual(r_active["score"], r_no["score"])

    def test_mental_health_returns_score(self):
        from deterministic_formulas import compute_mental_health
        result = compute_mental_health(self.profile, self.context, "Year1", stress_score=50, burnout_risk=35)
        self.assertIn("score", result)
        self.assertIn("narrative", result)

    def test_mental_health_declines_with_stress(self):
        from deterministic_formulas import compute_mental_health
        r_low = compute_mental_health(self.profile, self.context, "Year1", stress_score=30, burnout_risk=20)
        r_high = compute_mental_health(self.profile, self.context, "Year1", stress_score=80, burnout_risk=70)
        self.assertGreater(r_low["score"], r_high["score"])


class TestRelationshipFormulas(unittest.TestCase):
    """compute_family_stability, compute_social_connection, compute_relationship_wealth"""

    def setUp(self):
        self.profile = {}
        self.context = {"location": "Bangalore", "work_hours": 45}

    def test_family_stability_returns_score(self):
        from deterministic_formulas import compute_family_stability
        result = compute_family_stability(self.profile, self.context, "Year1")
        self.assertIn("score", result)
        self.assertIn("narrative", result)

    def test_social_connection_returns_score(self):
        from deterministic_formulas import compute_social_connection
        result = compute_social_connection(self.profile, self.context, "Year1")
        self.assertIn("score", result)

    def test_relationship_wealth_returns_index_and_narrative(self):
        from deterministic_formulas import compute_relationship_wealth
        result = compute_relationship_wealth(self.profile, self.context, family_score=60, social_score=65)
        self.assertIn("index", result)
        self.assertIn("narrative", result)


class TestOpportunityFormulas(unittest.TestCase):
    """compute_career_opportunities, compute_opportunity_score_forecast"""

    def setUp(self):
        self.profile = {}
        self.context = {"location": "Bangalore"}
        self.economic = {"industry_health": 78, "automation_risk": 15}

    def test_career_opportunities_returns_list(self):
        from deterministic_formulas import compute_career_opportunities
        result = compute_career_opportunities(self.profile, self.context, self.economic)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        for opp in result:
            self.assertIn("year", opp)
            self.assertIn("title", opp)
            self.assertIn("probability", opp)

    def test_career_opportunities_non_dict_economic(self):
        from deterministic_formulas import compute_career_opportunities
        result = compute_career_opportunities(self.profile, self.context, "bad_string")
        self.assertIsInstance(result, list)

    def test_opportunity_score_forecast_returns_list_of_year_scores(self):
        from deterministic_formulas import compute_opportunity_score_forecast
        result = compute_opportunity_score_forecast(self.profile, self.context, self.economic)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 5)
        for entry in result:
            self.assertIn("year", entry)
            self.assertIn("score", entry)

    def test_opportunity_score_forecast_non_dict_economic(self):
        from deterministic_formulas import compute_opportunity_score_forecast
        result = compute_opportunity_score_forecast(self.profile, self.context, None)
        self.assertIsInstance(result, list)


class TestEconomicForecastFormulas(unittest.TestCase):
    """compute_gdp_forecast, compute_salary_growth_forecast"""

    def setUp(self):
        self.profile = {}
        self.context = {"career_stage": "early"}
        self.economic = {"gdp_growth": 6.49, "industry_health": 78}

    def test_gdp_forecast_returns_list(self):
        from deterministic_formulas import compute_gdp_forecast
        result = compute_gdp_forecast(self.economic)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 5)
        for entry in result:
            self.assertIn("year", entry)
            self.assertIn("value", entry)
            self.assertIn("narrative", entry)

    def test_gdp_forecast_non_dict(self):
        from deterministic_formulas import compute_gdp_forecast
        result = compute_gdp_forecast(None)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 5)

    def test_salary_growth_forecast_returns_list(self):
        from deterministic_formulas import compute_salary_growth_forecast
        result = compute_salary_growth_forecast(self.profile, self.context, self.economic)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 5)

    def test_salary_growth_forecast_non_dict_economic(self):
        from deterministic_formulas import compute_salary_growth_forecast
        result = compute_salary_growth_forecast(self.profile, self.context, [])
        self.assertIsInstance(result, list)


class TestComputeYearScores(unittest.TestCase):
    """compute_year_scores — core simulation formula"""

    def setUp(self):
        self.profile = {}
        self.context = {"location": "Bangalore", "work_hours": 45, "risk_tolerance": "medium"}
        self.economic = {"gdp_growth": 6.49, "inflation_cpi": 4.95, "interest_rate": 6.5, "unemployment_rate": 4.22, "industry_health": 78, "automation_risk": 15}
        self.anchors = {"salary_lpa": 9.5, "work_hours": 45, "savings_rate": 44.3, "disposable_income": 35000, "stress_baseline": 55}

    def test_returns_all_7_nodes(self):
        from deterministic_formulas import compute_year_scores
        result = compute_year_scores(self.profile, self.context, self.economic, self.anchors, "Year1", "B")
        expected_keys = {"income", "career_growth", "stress", "health", "relationships", "happiness", "opportunity"}
        self.assertEqual(set(result.keys()), expected_keys)

    def test_scores_in_range(self):
        from deterministic_formulas import compute_year_scores
        result = compute_year_scores(self.profile, self.context, self.economic, self.anchors, "Year5", "C")
        for k, v in result.items():
            self.assertGreaterEqual(v, 10, f"{k}={v} below 10")
            self.assertLessEqual(v, 98, f"{k}={v} above 98")

    def test_personality_a_has_lower_stress(self):
        from deterministic_formulas import compute_year_scores
        r_a = compute_year_scores(self.profile, self.context, self.economic, self.anchors, "Year3", "A")
        r_c = compute_year_scores(self.profile, self.context, self.economic, self.anchors, "Year3", "C")
        self.assertLess(r_a["stress"], r_c["stress"])


class TestConfidence(unittest.TestCase):
    """compute_confidence"""

    def test_high_confidence(self):
        from deterministic_formulas import compute_confidence
        result = compute_confidence(85, 75, 20, 80)
        self.assertEqual(result["tier"], "high")
        self.assertGreaterEqual(result["overall"], 75)

    def test_medium_confidence(self):
        from deterministic_formulas import compute_confidence
        result = compute_confidence(60, 50, 40, 55)
        self.assertEqual(result["tier"], "medium")
        self.assertGreaterEqual(result["overall"], 50)
        self.assertLess(result["overall"], 75)

    def test_low_confidence(self):
        from deterministic_formulas import compute_confidence
        result = compute_confidence(30, 20, 60, 25)
        self.assertEqual(result["tier"], "low")

    def test_uncertainty_drivers_present(self):
        from deterministic_formulas import compute_confidence
        result = compute_confidence(40, 30, 60, 30)
        self.assertGreater(len(result["uncertainty_drivers"]), 0)

    def test_uncertainty_drivers_high_confidence(self):
        from deterministic_formulas import compute_confidence
        result = compute_confidence(90, 80, 10, 85)
        self.assertIn("High confidence across all dimensions.", result["uncertainty_drivers"])


if __name__ == "__main__":
    unittest.main()
