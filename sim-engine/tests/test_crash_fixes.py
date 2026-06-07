"""
Tests: Root cause crash fixes, type safety, decision normalization.

Run: python3 -m pytest tests/test_crash_fixes.py -v
Or:  python3 tests/test_crash_fixes.py
"""
import json
import os
import sys
import unittest
import types as pytypes
from unittest.mock import MagicMock, patch

# Mock google.genai before any sim-engine imports
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

# Silence noisy loggers during tests
import logging
logging.disable(logging.CRITICAL)


class TestNormalizeDecision(unittest.TestCase):
    """Step 5: Decision normalization for education paths."""

    def setUp(self):
        from career_profiles import normalize_decision
        self.normalize = normalize_decision

    def test_drop_out_of_college(self):
        result = self.normalize("drop out of college")
        self.assertIsNotNone(result)
        self.assertEqual(result["category"], "education")
        self.assertEqual(result["path"], "dropout")
        self.assertIn("profile_override", result)

    def test_drop_out_variant(self):
        result = self.normalize("I want to drop out of college")
        self.assertIsNotNone(result)
        self.assertEqual(result["path"], "dropout")

    def test_continue_college(self):
        result = self.normalize("continue it with a 6 CGPA")
        self.assertIsNotNone(result)
        self.assertEqual(result["path"], "continue_college")
        self.assertEqual(result["cgpa"], 6.0)

    def test_continue_without_cgpa(self):
        result = self.normalize("continue college")
        self.assertIsNotNone(result)
        self.assertEqual(result["path"], "continue_college")

    def test_mba(self):
        result = self.normalize("Should I do an MBA")
        self.assertIsNotNone(result)
        self.assertEqual(result["path"], "mba")

    def test_job(self):
        result = self.normalize("take a job")
        self.assertIsNotNone(result)
        self.assertEqual(result["path"], "job")

    def test_startup(self):
        result = self.normalize("start a startup")
        self.assertIsNotNone(result)
        self.assertEqual(result["path"], "startup")

    def test_unknown_option_returns_none(self):
        result = self.normalize("buy a car")
        self.assertIsNone(result)

    def test_higher_studies(self):
        result = self.normalize("pursue higher studies abroad")
        self.assertIsNotNone(result)
        self.assertEqual(result["category"], "education")


class TestDecisionProfileValidation(unittest.TestCase):
    """Step 7: Pydantic type-safe profiles."""

    def test_valid_profile(self):
        from career_profiles import DecisionProfile
        p = DecisionProfile(growth=8, salary_potential=9, risk=4, stress=5,
                           work_life_balance=6, demand=8, satisfaction=7, stability=7)
        self.assertEqual(p.growth, 8)

    def test_validate_profile_raises_on_string(self):
        from career_profiles import validate_profile
        with self.assertRaises(TypeError):
            validate_profile("this is a string", "test")

    def test_validate_profile_raises_on_none(self):
        from career_profiles import validate_profile
        with self.assertRaises(TypeError):
            validate_profile(None, "test")

    def test_validate_profile_accepts_dict(self):
        from career_profiles import validate_profile
        result = validate_profile({"growth": 7, "salary_potential": 8}, "test")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["growth"], 7.0)


class TestGetProfileWithNormalization(unittest.TestCase):
    """Step 5+6: Profile resolver with normalized paths."""

    def setUp(self):
        from career_profiles import get_profile
        self.get_profile = get_profile

    def test_dropout_gets_custom_profile(self):
        profile = self.get_profile("drop out of college", "educational")
        self.assertIsNotNone(profile)
        self.assertIsInstance(profile, dict)
        self.assertEqual(profile["growth"], 4)
        self.assertEqual(profile["risk"], 8)

    def test_continue_college_gets_custom_profile(self):
        profile = self.get_profile("continue college", "educational")
        self.assertIsNotNone(profile)
        self.assertIsInstance(profile, dict)
        self.assertEqual(profile["stability"], 7)

    def test_continue_with_cgpa_normalizes(self):
        profile = self.get_profile("continue it with a 6 CGPA", "educational")
        self.assertIsNotNone(profile)
        self.assertIsInstance(profile, dict)

    def test_get_profile_or_default_returns_dict_always(self):
        from career_profiles import get_profile_or_default
        for opt in ["drop out of college", "continue it with a 6 CGPA",
                     "buy a house", "move abroad", "", "CSE"]:
            result = get_profile_or_default(opt, "educational")
            self.assertIsInstance(result, dict,
                                  f"get_profile_or_default('{opt}') returned {type(result)}")


class TestBuildRecommendationFix(unittest.TestCase):
    """Step 1-4: Verify _build_recommendation no longer crashes on string values."""

    def test_string_comparison_values_no_longer_crash(self):
        from simulation_engine import _build_recommendation

        # This is the old format that caused the crash — string values mixed in
        comparison = {
            "Timeline A": {"overall_score": 55, "happiness_score": 55},
            "Timeline B": {"overall_score": 65, "happiness_score": 65},
            "Timeline C": {"overall_score": 50, "happiness_score": 50},
            "common_patterns": "All paths share the same starting conditions.",
            "key_differences": "Timeline B leads in income.",
            "hinge_point": "The decision itself.",
        }
        analysis = {"summary": {"career_path": "Engineer"}}

        result = _build_recommendation(analysis, comparison)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["primary_path"], "Timeline B")

    def test_empty_comparison_returns_empty(self):
        from simulation_engine import _build_recommendation
        result = _build_recommendation({}, {})
        self.assertEqual(result, {})

    def test_only_string_values_returns_fallback(self):
        from simulation_engine import _build_recommendation
        comparison = {
            "common_patterns": "text",
            "key_differences": "text",
            "hinge_point": "text",
        }
        result = _build_recommendation({}, comparison)
        # Should fall through to default Timeline B since all entries are strings
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("primary_path"), "Timeline B")


class TestFallbackComparisonFormat(unittest.TestCase):
    """Verify _fallback_comparison now returns timeline-keyed scores."""

    def test_returns_timeline_scores_and_text_fields(self):
        from agents.synthesis import _fallback_comparison

        timelines = {
            "Timeline A": {
                "Year1": {"income": 30, "happiness": 50},
                "_causal": {"Year10": {"income": 50, "happiness": 55, "stress": 40,
                                        "career_growth": 45}},
            },
            "Timeline B": {
                "Year1": {"income": 35, "happiness": 55},
                "_causal": {"Year10": {"income": 70, "happiness": 65, "stress": 50,
                                        "career_growth": 60}},
            },
            "Timeline C": {
                "Year1": {"income": 40, "happiness": 50},
                "_causal": {"Year10": {"income": 85, "happiness": 60, "stress": 70,
                                        "career_growth": 75}},
            },
        }

        result = _fallback_comparison(timelines)

        # Should have per-timeline score entries
        self.assertIn("Timeline A", result)
        self.assertIn("Timeline B", result)
        self.assertIn("Timeline C", result)

        # Each timeline entry should be a dict with scores
        for tl_key in ["Timeline A", "Timeline B", "Timeline C"]:
            self.assertIsInstance(result[tl_key], dict)
            self.assertIn("overall_score", result[tl_key])
            self.assertIn("happiness_score", result[tl_key])
            self.assertIn("income_score", result[tl_key])

        # Should also have text fields
        self.assertIsInstance(result.get("common_patterns"), str)
        self.assertIsInstance(result.get("key_differences"), str)
        self.assertIsInstance(result.get("hinge_point"), str)


class TestQuotaManagerSynthesisGuard(unittest.TestCase):
    """Synthesis should not be blocked by offline quota mode."""

    def test_synthesis_stays_enabled_in_offline_mode(self):
        from quota_manager import QuotaManager

        qm = QuotaManager(state_file="/tmp/quota_manager_test_state.json")
        qm.state["mode"] = "offline"

        self.assertTrue(qm.should_use_llm("synthesis"))
        self.assertFalse(qm.should_use_llm("timeline"))


class TestValidateSimulationInput(unittest.TestCase):
    """Step 8+9: Input validation layer."""

    def test_valid_anchors_passes(self):
        from simulation_engine import validate_simulation_input
        anchors = {
            "income_anchors": {10: 2.0},
            "opportunity_base": 82,
            "psychographic_bases": {"stress": 55},
            "prompt_block": "test",
            "_computed": {"salary": 10},
            "_grounding": {"role": "engineer"},
        }
        result = validate_simulation_input(anchors)
        self.assertIs(result, anchors)

    def test_none_anchors_raises(self):
        from simulation_engine import validate_simulation_input
        with self.assertRaises(TypeError):
            validate_simulation_input(None)

    def test_string_anchors_raises(self):
        from simulation_engine import validate_simulation_input
        with self.assertRaises(TypeError):
            validate_simulation_input("I am a string")

    def test_wrong_computed_type_raises(self):
        from simulation_engine import validate_simulation_input
        anchors = {
            "income_anchors": {10: 2.0},
            "opportunity_base": 82,
            "psychographic_bases": {"stress": 55},
            "prompt_block": "test",
            "_computed": "I should be a dict",
        }
        with self.assertRaises(TypeError):
            validate_simulation_input(anchors)


class TestValidateProfileBeforeUse(unittest.TestCase):
    """Step 9: Defensive profile checks."""

    def test_dict_passes(self):
        from simulation_engine import _validate_profile_before_use
        result = _validate_profile_before_use({"a": 1}, "test")
        self.assertEqual(result, {"a": 1})

    def test_string_raises(self):
        from simulation_engine import _validate_profile_before_use
        with self.assertRaises(TypeError):
            _validate_profile_before_use("I am a string", "test")

    def test_none_raises(self):
        from simulation_engine import _validate_profile_before_use
        with self.assertRaises(TypeError):
            _validate_profile_before_use(None, "test")


class TestEducationalDecisionFlow(unittest.TestCase):
    """Step 10: Integration tests for educational decisions."""

    def test_dropout_vs_continue_using_make_option_comparison(self):
        from simulation_engine import make_option_comparison
        from decision_parser import parse_decision

        decision = "Should I drop out of college or continue it with a 6 CGPA"
        parsed = parse_decision(decision)
        context = {"age": 20, "location": "India"}

        result = make_option_comparison(decision, context, parsed=parsed)
        self.assertIn("options", result)
        self.assertIn("winner", result)
        self.assertIn("profiles", result)
        self.assertEqual(len(result["profiles"]), 2)
        for pd in result["profiles"]:
            self.assertIsInstance(pd["profile"], dict)
            self.assertIsInstance(pd["scores"], dict)

    def test_mba_vs_job(self):
        from simulation_engine import make_option_comparison
        from decision_parser import parse_decision

        decision = "Should I do an MBA or take a job?"
        parsed = parse_decision(decision)
        context = {"age": 23, "location": "Bangalore"}

        result = make_option_comparison(decision, context, parsed=parsed)
        self.assertIn("winner", result)
        self.assertIn("profiles", result)
        for pd in result["profiles"]:
            self.assertIsInstance(pd["profile"], dict)

    def test_cse_vs_aiml(self):
        from simulation_engine import make_option_comparison
        from decision_parser import parse_decision

        decision = "CSE vs AIML at VIT?"
        parsed = parse_decision(decision)
        context = {"age": 18, "location": "Vellore"}

        result = make_option_comparison(decision, context, parsed=parsed)
        self.assertIn("winner", result)
        self.assertEqual(len(result["profiles"]), 2)

    def test_startup_vs_mnc(self):
        from simulation_engine import make_option_comparison
        from decision_parser import parse_decision

        decision = "Should I join a startup or an MNC?"
        parsed = parse_decision(decision)
        context = {"age": 25, "location": "Bangalore"}

        result = make_option_comparison(decision, context, parsed=parsed)
        self.assertIn("winner", result)

    def test_move_abroad_vs_stay(self):
        from simulation_engine import make_option_comparison
        from decision_parser import parse_decision

        decision = "Should I move abroad or stay in India?"
        parsed = parse_decision(decision)
        context = {"age": 28, "location": "Mumbai"}

        result = make_option_comparison(decision, context, parsed=parsed)
        self.assertIn("winner", result)
        for pd in result["profiles"]:
            self.assertIsInstance(pd["scores"], dict)


class TestTimelineChaosSafety(unittest.TestCase):
    """Regression tests for malformed chaos events passed into timeline generation."""

    def test_apply_chaos_deltas_ignores_string_events(self):
        from agents.timeline import _apply_chaos_deltas

        scores = {"income": 50, "stress": 50}
        result = _apply_chaos_deltas(
            scores,
            [
                "Stayed in college",
                {"year": "Year1", "node_deltas": {"income": 5}},
            ],
            "Year1",
        )

        self.assertEqual(result["income"], 55)
        self.assertEqual(result["stress"], 50)


class TestFullSimulationWithMockedLiveData(unittest.TestCase):
    """Run full simulation pipeline with educational decision."""

    @patch.dict(os.environ, {"USE_DATA_GROUNDING": "false"})
    def test_run_simulation_dropout_decision_no_crash(self):
        """Core fix test: run_simulation with dropout decision must not crash."""
        from simulation_engine import run_simulation

        decision = "Should I drop out of college or continue it with a 6 CGPA"
        context = {"age": 20, "location": "India"}

        try:
            result = run_simulation(
                decision=decision,
                context=context,
                chaos_events=None,
                llm_format=False,
                llm_formatter=None,
            )
            self.assertIsInstance(result, dict)
            self.assertIn("timelines", result)
            self.assertIn("synthesis", result)
            self.assertIn("comparison", result)
            self.assertIn("recommendation",
                          result.get("synthesis", {}))
        except Exception as e:
            self.fail(f"run_simulation raised: {type(e).__name__}: {e}")

    @patch.dict(os.environ, {"USE_DATA_GROUNDING": "false"})
    def test_run_simulation_cse_vs_aiml(self):
        from simulation_engine import run_simulation
        result = run_simulation(
            decision="CSE vs AIML at VIT in 2026?",
            context={"age": 18, "location": "Vellore"},
            chaos_events=None,
        )
        self.assertIn("timelines", result)
        self.assertIn("decision_parsing", result)

    @patch.dict(os.environ, {"USE_DATA_GROUNDING": "false"})
    def test_run_simulation_mba_vs_work(self):
        from simulation_engine import run_simulation
        result = run_simulation(
            decision="Should I do an MBA or work for 2 more years?",
            context={"age": 23, "location": "Bangalore"},
            chaos_events=None,
        )
        self.assertIn("timelines", result)

    @patch.dict(os.environ, {"USE_DATA_GROUNDING": "false"})
    def test_run_simulation_single_option(self):
        """Decisions with only one parsed option should not crash."""
        from simulation_engine import run_simulation
        result = run_simulation(
            decision="Should I start a company?",
            context={"age": 25, "location": "Bangalore"},
            chaos_events=None,
        )
        self.assertIn("timelines", result)

    @patch.dict(os.environ, {"USE_DATA_GROUNDING": "false"})
    def test_run_simulation_abroad_decision(self):
        from simulation_engine import run_simulation
        result = run_simulation(
            decision="Should I move abroad or stay in India?",
            context={"age": 28, "location": "Mumbai", "skills": "Software Engineering"},
            chaos_events=None,
        )
        self.assertIn("timelines", result)


if __name__ == "__main__":
    unittest.main()
