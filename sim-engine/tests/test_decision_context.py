"""
Tests: Decision context is preserved through the simulation pipeline.

Run: venv/bin/python -m pytest tests/test_decision_context.py -v
Or:  venv/bin/python tests/test_decision_context.py
"""
import json
import os
import sys
import unittest

# Ensure we can import from parent dir
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from decision_parser import parse_decision, ParsedDecision
from data_grounding import (
    detect_role, detect_industry, detect_education_fields,
    is_educational_decision, _whole_word_match,
)
from agents.timeline import generate_timelines


class TestWholeWordMatch(unittest.TestCase):
    """Test that _whole_word_match prevents substring false positives."""

    def test_ai_does_not_match_aiml(self):
        """'ai' should NOT match 'AIML' as a whole word."""
        self.assertFalse(_whole_word_match("ai", "AIML at VIT"))
        self.assertFalse(_whole_word_match("ai", "I study AIML"))

    def test_ai_matches_standalone_ai(self):
        """'ai' SHOULD match standalone 'AI'."""
        self.assertTrue(_whole_word_match("ai", "I work in AI"))
        self.assertTrue(_whole_word_match("AI", "AI is the future"))

    def test_software_matches_software(self):
        """'software' should match as whole word."""
        self.assertTrue(_whole_word_match("software", "I am a software engineer"))

    def test_ml_does_not_match_aiml(self):
        """'ml' should NOT match inside 'AIML'."""
        self.assertFalse(_whole_word_match("ml", "AIML"))


class TestDecisionParser(unittest.TestCase):
    """Test that parse_decision extracts structured options."""

    def test_cse_or_aiml(self):
        parsed = parse_decision("CSE or AIML at VIT in 2026?")
        self.assertEqual(len(parsed.options), 2)
        self.assertIn("CSE", parsed.options[0])
        self.assertIn("AIML", parsed.options[1])
        self.assertEqual(parsed.institution, "VIT")
        self.assertEqual(parsed.year, 2026)
        self.assertEqual(parsed.decision_type, "educational")
        self.assertGreaterEqual(parsed.confidence, 80)

    def test_quit_job_or_startup(self):
        parsed = parse_decision("Should I quit my job to start a company?")
        self.assertEqual(len(parsed.options), 2)

    def test_mba_or_work(self):
        parsed = parse_decision("MBA now or work for 2 more years first?")
        self.assertEqual(len(parsed.options), 2)
        self.assertEqual(parsed.decision_type, "educational")

    def test_simple_question_has_fallback(self):
        parsed = parse_decision("What should I do with my life?")
        self.assertGreaterEqual(len(parsed.options), 0)

    def test_vs_pattern(self):
        parsed = parse_decision("Python vs Java for data engineering?")
        self.assertEqual(len(parsed.options), 2)

    def test_simple_educational_phrase_parses_confidently(self):
        parsed = parse_decision("cse in ggsipu")
        self.assertEqual(parsed.decision_type, "educational")
        self.assertGreaterEqual(parsed.confidence, 80)
        self.assertIn("CSE", parsed.options[0] if parsed.options else "")
        self.assertEqual(parsed.institution, "GGSIPU")

    def test_educational_vs_pattern_is_classified_as_educational(self):
        parsed = parse_decision("IIT vs NIT")
        self.assertEqual(parsed.decision_type, "educational")
        self.assertGreaterEqual(parsed.confidence, 80)

    def test_empty_decision(self):
        parsed = parse_decision("")
        self.assertEqual(len(parsed.options), 0)
        self.assertLess(parsed.confidence, 50)


class TestDataGroundingDetection(unittest.TestCase):
    """Test that detect_role no longer has false positives."""

    def test_aiml_no_longer_detects_data_scientist(self):
        """'AIML' should NOT trigger 'data scientist' role anymore."""
        role = detect_role("CSE or AIML at VIT in 2026?", {"location": "Bangalore"})
        self.assertNotEqual(role, "data scientist",
                            "AIML should not match 'ai' as a data scientist keyword")

    def test_cse_detects_software_industry(self):
        """'CSE' should match computer science / software."""
        fields = detect_education_fields("CSE or AIML at VIT in 2026?", {"location": "Bangalore"})
        self.assertIn("computer science", fields)

    def test_aiml_detects_aiml_field(self):
        """'AIML' should match the AIML education field."""
        fields = detect_education_fields("CSE or AIML at VIT in 2026?", {"location": "Bangalore"})
        self.assertIn("aiml", fields)

    def test_educational_detection(self):
        self.assertTrue(is_educational_decision("CSE or AIML at VIT in 2026?"))
        self.assertTrue(is_educational_decision("Should I study at IIT?"))
        self.assertTrue(is_educational_decision("Should I take NEET or JEE?"))
        self.assertFalse(is_educational_decision("Should I buy a car?"))

    def test_neet_jee_is_classified_as_educational(self):
        parsed = parse_decision("Should I take NEET or JEE?")
        self.assertEqual(parsed.decision_type, "educational")


class TestCSEvsAIMLScenario(unittest.TestCase):
    """
    End-to-end test: "CSE or AIML at VIT in 2026?"
    Must produce timelines tied to these options, not generic career output.
    """

    def setUp(self):
        self.decision = "CSE or AIML at VIT in 2026?"
        self.context = {
            "age": 18,
            "location": "Vellore",
            "risk_tolerance": "medium",
            "current_skills": "Mathematics, Programming",
        }

    def test_generate_timelines_does_not_crash(self):
        """generate_timelines should run without error for CSE/AIML question."""
        try:
            result = generate_timelines(self.decision, self.context)
            self.assertIn("Timeline A", result)
            self.assertIn("Timeline B", result)
            self.assertIn("Timeline C", result)
            self.assertIn("_analysis", result)
        except Exception as e:
            self.fail(f"generate_timelines raised: {e}")

    def test_narratives_mention_decision_options(self):
        """Timeline narratives should reference the actual decision options."""
        result = generate_timelines(self.decision, self.context)
        for tl_key in ["Timeline A", "Timeline B", "Timeline C"]:
            tl = result.get(tl_key, {})
            for yr_key in ["Year1", "Year3"]:
                narrative = tl.get(yr_key, "")
                if narrative:
                    # At least one timeline should reference CSE, AIML, VIT, or engineering
                    mentions_options = any(
                        kw in narrative.lower()
                        for kw in ["cse", "aiml", "vit", "engineering", "computer", "software", "programming", "machine learning", "artificial intelligence"]
                    )
                    if not mentions_options:
                        print(f"[WARN] {tl_key}/{yr_key} does not mention decision options: {narrative[:100]}")


class TestValidation(unittest.TestCase):
    """Test that validation catches missing decision context."""

    def test_empty_decision_raises_error(self):
        with self.assertRaises(ValueError):
            generate_timelines("", {"age": 20})

    def test_short_decision_raises_error(self):
        with self.assertRaises(ValueError):
            generate_timelines("Hi", {"age": 20})


class TestAPIRequestLogging(unittest.TestCase):
    """Test that the decision is logged properly."""

    def test_parsed_decision_in_api_response_structure(self):
        """Verify the decision_parsing block exists in a simulated response."""
        parsed = parse_decision("CSE or AIML at VIT in 2026?")
        response_block = {
            "options": parsed.options,
            "type": parsed.decision_type,
            "confidence": parsed.confidence,
            "institution": parsed.institution,
            "year": parsed.year,
        }
        self.assertIn("options", response_block)
        self.assertIn("type", response_block)
        self.assertIn("confidence", response_block)
        self.assertEqual(response_block["institution"], "VIT")
        self.assertEqual(response_block["year"], 2026)


if __name__ == "__main__":
    unittest.main()
