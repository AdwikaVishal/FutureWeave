"""
Production-grade base LLM Agent for FutureWeave LangGraph multi-agent system.
Provides prompt loading, LLM calling with quota tracking, caching, retry, and metrics.
"""
import json
import logging
import os
import time
from typing import Any, Callable, Optional

from llm_client import call_llm
from llm_cache import get_cache
from quota_manager import get_quota_manager
from input_validator import safe_template_substitute

logger = logging.getLogger(__name__)


class LLMAgent:
    def __init__(self, name: str, prompt_file: str, temperature: float = 0.7):
        self.name = name
        self.prompt_file = prompt_file
        self.temperature = temperature
        self._prompt_template = None
        self._metrics = {"calls": 0, "cache_hits": 0, "failures": 0, "total_latency_ms": 0.0}

    def _load_prompt(self) -> str:
        if self._prompt_template is None:
            path = os.path.join(os.path.dirname(__file__), "..", "prompts", self.prompt_file)
            with open(path) as f:
                self._prompt_template = f.read()
        return self._prompt_template

    def load_prompt(self) -> str:
        return self._load_prompt()

    def build_prompt(self, **kwargs: Any) -> str:
        template = self._load_prompt()
        safe_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, (dict, list)):
                safe_kwargs[k] = json.dumps(v, indent=2, default=str)
            elif v is None:
                safe_kwargs[k] = "N/A"
            else:
                safe_kwargs[k] = str(v)
        return safe_template_substitute(template, **safe_kwargs)

    def run(self, prompt: str, use_cache: bool = True) -> str:
        qm = get_quota_manager()
        cache = get_cache()

        if use_cache:
            cached = cache.get(prompt, self.name)
            if cached is not None:
                self._metrics["cache_hits"] += 1
                logger.info("[%s] Cache hit | prompt_len=%d | response_len=%d",
                           self.name, len(prompt), len(cached))
                return cached

        self._metrics["calls"] += 1
        start = time.time()
        try:
            logger.info("[%s] >>> LLM call | prompt_len=%d | temp=%.2f",
                       self.name, len(prompt), self.temperature)
            raw = call_llm(prompt, temperature=self.temperature)
            latency = (time.time() - start) * 1000
            self._metrics["total_latency_ms"] += latency
            qm.record_call(latency_ms=latency)
            logger.info("[%s] <<< LLM success | len=%d | %.0fms",
                       self.name, len(raw), latency)

            if use_cache:
                cache.set(prompt, self.name, raw)
            return raw

        except Exception as exc:
            latency = (time.time() - start) * 1000
            self._metrics["failures"] += 1
            self._metrics["total_latency_ms"] += latency
            is_rate = "429" in str(exc) or "rate limit" in str(exc).lower()
            qm.record_error(is_rate_limit=is_rate)
            logger.error("[%s] LLM failed after %.0fms: %s | rate_limit=%s",
                        self.name, latency, exc, is_rate)
            raise

    def run_structured(
        self,
        prompt: str,
        parser: Optional[Callable[[str], dict]] = None,
        use_cache: bool = True,
    ) -> dict:
        raw = self.run(prompt, use_cache=use_cache)
        if not raw or not raw.strip():
            logger.warning("[%s] LLM returned empty response", self.name)
            raise ValueError("Empty LLM response")
        if parser:
            return parser(raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("[%s] LLM returned non-JSON, attempting repair", self.name)
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(l for l in lines if not l.strip().startswith("```"))
            start_b = cleaned.find("{")
            end_b = cleaned.rfind("}")
            if start_b != -1 and end_b > start_b:
                cleaned = cleaned[start_b:end_b+1]
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"LLM response is not valid JSON: {raw[:200]}")

    def metrics(self) -> dict:
        return dict(self._metrics)

    @staticmethod
    def format_dict(d: Any) -> str:
        if isinstance(d, str):
            return d
        return json.dumps(d, indent=2, default=str)
