"""
Tests: llm_client.py — ProviderRouter, clean_json, retry logic, fallback.

Run: python3 -m pytest tests/test_llm_client.py -v
Or:  python3 tests/test_llm_client.py
"""
import json
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


class TestCleanJson(unittest.TestCase):
    """clean_json — strip markdown fences and extract JSON"""

    def test_passes_clean_json(self):
        from llm_client import clean_json
        raw = '{"key": "value"}'
        self.assertEqual(clean_json(raw), raw)

    def test_strips_markdown_fences(self):
        from llm_client import clean_json
        raw = '```json\n{"key": "value"}\n```'
        self.assertEqual(clean_json(raw), '{"key": "value"}')

    def test_strips_plain_triple_backtick(self):
        from llm_client import clean_json
        raw = '```\n{"key": "value"}\n```'
        self.assertEqual(clean_json(raw), '{"key": "value"}')

    def test_extracts_json_from_surrounding_text(self):
        from llm_client import clean_json
        raw = 'Here is the result:\n{"key": "value"}\nEnd.'
        self.assertEqual(clean_json(raw), '{"key": "value"}')

    def test_handles_nested_braces(self):
        from llm_client import clean_json
        raw = '{"outer": {"inner": "value"}}'
        self.assertEqual(clean_json(raw), raw)

    def test_returns_empty_on_no_braces(self):
        from llm_client import clean_json
        self.assertEqual(clean_json("just text"), "just text")


class TestIsRateLimit(unittest.TestCase):
    """_is_rate_limit"""

    def test_429_status(self):
        from llm_client import _is_rate_limit
        self.assertTrue(_is_rate_limit(Exception("429 Too Many Requests")))

    def test_rate_limit_text(self):
        from llm_client import _is_rate_limit
        self.assertTrue(_is_rate_limit(Exception("rate limit exceeded")))

    def test_resource_exhausted(self):
        from llm_client import _is_rate_limit
        self.assertTrue(_is_rate_limit(Exception("resource exhausted")))

    def test_other_error(self):
        from llm_client import _is_rate_limit
        self.assertFalse(_is_rate_limit(Exception("server error 500")))


class TestRetryDelay(unittest.TestCase):
    """_retry_delay"""

    def test_increases_with_attempt(self):
        from llm_client import _retry_delay
        d1 = _retry_delay(0)
        d2 = _retry_delay(1)
        d3 = _retry_delay(2)
        self.assertLess(d1, d2)
        self.assertLess(d2, d3)

    def test_capped_at_max(self):
        from llm_client import _retry_delay
        d = _retry_delay(10)
        self.assertLessEqual(d, 20.0)


class TestIsValidLlmOutput(unittest.TestCase):
    """_is_valid_llm_output"""

    def test_valid_json_object(self):
        from llm_client import _is_valid_llm_output
        self.assertTrue(_is_valid_llm_output('{"result": "ok"}'))

    def test_too_short(self):
        from llm_client import _is_valid_llm_output
        self.assertFalse(_is_valid_llm_output(""))

    def test_unclosed_brace(self):
        from llm_client import _is_valid_llm_output
        self.assertFalse(_is_valid_llm_output('{"a": 1'))


class TestGetProviderOrder(unittest.TestCase):
    """_get_provider_order"""

    @patch.dict(os.environ, {}, clear=True)
    def test_default_order(self):
        from llm_client import _get_provider_order
        order = _get_provider_order()
        self.assertEqual(order, ["openai", "gemini", "groq", "openrouter", "anthropic"])

    @patch.dict(os.environ, {"LLM_PROVIDER_PRIORITY": "groq,openai"}, clear=True)
    def test_custom_order(self):
        from llm_client import _get_provider_order
        order = _get_provider_order()
        self.assertEqual(order, ["groq", "openai"])

    @patch.dict(os.environ, {"LLM_PROVIDER_PRIORITY": "invalid_provider"}, clear=True)
    def test_unknown_provider_filtered(self):
        from llm_client import _get_provider_order
        order = _get_provider_order()
        self.assertEqual(order, ["openai", "gemini", "groq", "openrouter", "anthropic"])


class TestProviderHasKey(unittest.TestCase):
    """_provider_has_key"""

    def test_openai_needs_key(self):
        from llm_client import _provider_has_key
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
            self.assertFalse(_provider_has_key("openai"))
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            self.assertTrue(_provider_has_key("openai"))

    def test_gemini_needs_key(self):
        from llm_client import _provider_has_key
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=True):
            self.assertFalse(_provider_has_key("gemini"))
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            self.assertTrue(_provider_has_key("gemini"))

    def test_unknown_provider(self):
        from llm_client import _provider_has_key
        self.assertFalse(_provider_has_key("nonexistent"))


class TestCallLlm(unittest.TestCase):
    """call_llm — full provider routing"""

    def setUp(self):
        self.cache_patcher = patch("llm_client.get_cache")
        self.mock_cache = self.cache_patcher.start()
        self.mock_cache_instance = MagicMock()
        self.mock_cache.return_value = self.mock_cache_instance
        self.mock_cache_instance.get.return_value = None

        self.env_patcher = patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-test",
            "GEMINI_API_KEY": "",
            "GROQ_API_KEY": "",
            "OPENROUTER_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
        }, clear=True)
        self.env_patcher.start()

        # Mock PROVIDERS to bypass real SDK imports
        self.providers_patcher = patch("llm_client.PROVIDERS", {})
        self.mock_providers = self.providers_patcher.start()

    def tearDown(self):
        self.cache_patcher.stop()
        self.env_patcher.stop()
        self.providers_patcher.stop()

    def test_calls_openai_when_key_present(self):
        from llm_client import call_llm
        mock_fn = MagicMock(return_value='{"result": "ok"}')
        self.mock_providers["openai"] = mock_fn
        result = call_llm("test prompt")
        mock_fn.assert_called_once()
        self.assertIn("result", result)

    def test_falls_through_when_first_fails(self):
        from llm_client import call_llm
        self.mock_providers["openai"] = MagicMock(side_effect=RuntimeError("OpenAI down"))
        self.mock_providers["gemini"] = MagicMock(return_value='{"result": "gemini_ok"}')
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=True):
            result = call_llm("test prompt")
            self.assertIn("gemini_ok", result)

    def test_returns_cached_response(self):
        from llm_client import call_llm
        mock_fn = MagicMock()
        self.mock_providers["openai"] = mock_fn
        self.mock_cache_instance.get.return_value = '{"cached": true}'
        result = call_llm("test prompt")
        mock_fn.assert_not_called()
        self.assertIn("cached", result)

    def test_raises_when_all_providers_fail(self):
        from llm_client import call_llm
        self.mock_providers["openai"] = MagicMock(side_effect=RuntimeError("all down"))
        with self.assertRaises(RuntimeError):
            call_llm("test prompt")


class TestCallLlmWithFallback(unittest.TestCase):
    """call_llm_with_fallback"""

    @patch("llm_client.call_llm")
    def test_returns_llm_result_on_success(self, mock_call_llm):
        from llm_client import call_llm_with_fallback
        mock_call_llm.return_value = '{"ok": true}'
        result = call_llm_with_fallback("test")
        self.assertEqual(result, '{"ok": true}')

    @patch("llm_client.call_llm")
    def test_returns_fallback_on_failure(self, mock_call_llm):
        from llm_client import call_llm_with_fallback
        mock_call_llm.side_effect = RuntimeError("fail")
        result = call_llm_with_fallback("test", fallback_text='{"fallback": true}')
        self.assertEqual(result, '{"fallback": true}')


class TestCallGroqRetry(unittest.TestCase):
    """call_groq — retry logic"""

    @patch("litellm.completion")
    def test_succeeds_on_first_attempt(self, mock_completion):
        from llm_client import call_groq
        mock_completion.return_value.choices[0].message.content = '{"ok": true}'
        result = call_groq("test")
        self.assertIn("ok", result)
        self.assertEqual(mock_completion.call_count, 1)

    @patch("litellm.completion")
    def test_retries_on_rate_limit(self, mock_completion):
        from llm_client import call_groq
        mock_completion.side_effect = [
            Exception("429 rate limit"),
            MagicMock(choices=[MagicMock(message=MagicMock(content='{"ok": true}'))]),
        ]
        result = call_groq("test")
        self.assertIn("ok", result)
        self.assertEqual(mock_completion.call_count, 2)

    @patch("litellm.completion")
    def test_raises_after_max_retries(self, mock_completion):
        from llm_client import call_groq
        mock_completion.side_effect = Exception("persistent failure")
        with self.assertRaises(Exception):
            call_groq("test")


if __name__ == "__main__":
    unittest.main()
