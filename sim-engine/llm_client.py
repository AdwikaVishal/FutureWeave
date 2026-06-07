"""
Production-grade LLM client with ProviderRouter:
OpenAI → Gemini → Groq → OpenRouter → Anthropic
with exponential backoff, caching, structured logging, and graceful degradation.
"""
import json
import logging
import os
import random
import re
import time
from typing import Optional, Callable

from dotenv import load_dotenv

load_dotenv()

from llm_cache import get_cache

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_RETRY_BASE_SEC = 1.0
_RETRY_MAX_SEC = 20.0

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "groq/llama-3.3-70b-versatile")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

PROVIDER_PRIORITY = os.environ.get("LLM_PROVIDER_PRIORITY",
                                   "openai,gemini,groq,openrouter,anthropic")

_gemini_client = None


def clean_json(raw: str) -> str:
    raw = re.sub(r'```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```', '', raw)
    start = raw.find('{')
    end = raw.rfind('}')
    if start != -1 and end != -1 and end > start:
        raw = raw[start:end + 1]
    return raw.strip()


def _is_rate_limit(err: Exception) -> bool:
    s = str(err).lower()
    return any(x in s for x in ("429", "rate limit", "resource exhausted", "too many requests",
                                 "quota", "insufficient_quota"))


def _retry_delay(attempt: int) -> float:
    base = _RETRY_BASE_SEC * (2 ** attempt)
    jitter = random.uniform(0, base * 0.3)
    return min(base + jitter, _RETRY_MAX_SEC)


def _is_valid_llm_output(text: str) -> bool:
    if not text or len(text.strip()) < 10:
        return False
    if text.startswith('{') and not text.endswith('}'):
        return False
    return True


# ── Individual Providers ──────────────────────────────────────────────────────

def call_openai(prompt: str, temperature: float = 0.7) -> str:
    from openai import OpenAI
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=api_key)
    logger.info("[LLM] >>> OpenAI | model=%s | prompt_len=%d", OPENAI_MODEL, len(prompt))
    start = time.time()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        timeout=30,
    )
    elapsed = (time.time() - start) * 1000
    raw = response.choices[0].message.content or ""
    logger.info("[LLM] <<< OpenAI | len=%d | %.0fms", len(raw), elapsed)
    return clean_json(raw)


def call_gemini(prompt: str, temperature: float = 0.7) -> str:
    global _gemini_client
    from google import genai
    from google.genai import types as genai_types

    if _gemini_client is None:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        _gemini_client = genai.Client(api_key=api_key)

    logger.info("[LLM] >>> Gemini | model=%s | prompt_len=%d", GEMINI_MODEL, len(prompt))
    start = time.time()
    response = _gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=genai_types.GenerateContentConfig(temperature=temperature),
    )
    elapsed = (time.time() - start) * 1000
    raw = response.text
    logger.info("[LLM] <<< Gemini | len=%d | %.0fms", len(raw), elapsed)
    return clean_json(raw)


def call_groq(prompt: str, temperature: float = 0.7) -> str:
    from litellm import completion
    last_err = None
    for attempt in range(_MAX_RETRIES):
        try:
            logger.info("[LLM] >>> Groq attempt %d/%d | prompt_len=%d",
                        attempt + 1, _MAX_RETRIES, len(prompt))
            start = time.time()
            response = completion(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                timeout=30,
            )
            elapsed = (time.time() - start) * 1000
            raw = response.choices[0].message.content or ""
            logger.info("[LLM] <<< Groq | len=%d | %.0fms", len(raw), elapsed)
            return clean_json(raw)
        except Exception as err:
            last_err = err
            delay = _retry_delay(attempt)
            logger.warning("[LLM] Groq attempt %d failed: %s | retry in %.1fs",
                           attempt + 1, err, delay)
            if _is_rate_limit(err) or attempt < _MAX_RETRIES - 1:
                time.sleep(delay)
                continue
            break
    raise last_err


def call_openrouter(prompt: str, temperature: float = 0.7) -> str:
    from openai import OpenAI
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )
    logger.info("[LLM] >>> OpenRouter | model=%s | prompt_len=%d", OPENROUTER_MODEL, len(prompt))
    start = time.time()
    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        timeout=30,
    )
    elapsed = (time.time() - start) * 1000
    raw = response.choices[0].message.content or ""
    logger.info("[LLM] <<< OpenRouter | len=%d | %.0fms", len(raw), elapsed)
    return clean_json(raw)


def call_anthropic(prompt: str, temperature: float = 0.7) -> str:
    from anthropic import Anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = Anthropic(api_key=api_key)
    logger.info("[LLM] >>> Anthropic | model=%s | prompt_len=%d", ANTHROPIC_MODEL, len(prompt))
    start = time.time()
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    elapsed = (time.time() - start) * 1000
    raw = response.content[0].text if response.content else ""
    logger.info("[LLM] <<< Anthropic | len=%d | %.0fms", len(raw), elapsed)
    return clean_json(raw)


# ── Provider Registry ─────────────────────────────────────────────────────────

PROVIDERS = {
    "openai": call_openai,
    "gemini": call_gemini,
    "groq": call_groq,
    "openrouter": call_openrouter,
    "anthropic": call_anthropic,
}


def _get_provider_order() -> list[str]:
    order = os.environ.get("LLM_PROVIDER_PRIORITY", "openai,gemini,groq,openrouter,anthropic")
    configured = [p.strip() for p in order.split(",") if p.strip() in PROVIDERS]
    if not configured:
        configured = ["openai", "gemini", "groq", "openrouter", "anthropic"]
    return configured


def _provider_has_key(provider: str) -> bool:
    key_map = {
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "groq": "GROQ_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }
    env_var = key_map.get(provider)
    if not env_var:
        return False
    return bool(os.environ.get(env_var, "").strip())


# ── Provider Health Check ──────────────────────────────────────────────────────

def check_provider_health() -> dict:
    """Check which LLM providers are configured (API key present, no actual calls)."""
    results = {}
    for provider in PROVIDERS:
        has_key = _provider_has_key(provider)
        results[provider] = {"configured": has_key}
        if has_key:
            results[provider]["model"] = os.environ.get(f"{provider.upper()}_MODEL", "")
    return results


def any_provider_healthy() -> bool:
    """Return True if at least one LLM provider has an API key configured."""
    health = check_provider_health()
    return any(v.get("configured") for v in health.values())


# ── Public API ────────────────────────────────────────────────────────────────

def call_llm(prompt: str, temperature: float = 0.7) -> str:
    from quota_manager import get_quota_manager
    qm = get_quota_manager()
    if qm.mode == "offline":
        raise RuntimeError("Quota manager is in offline mode — skipping LLM calls")

    cache = get_cache()
    provider_order = _get_provider_order()

    cached = cache.get(prompt, "llm")
    if cached:
        logger.info("[LLM] Cache hit — returning cached response (%d chars)", len(cached))
        return cached

    errors = []
    for provider in provider_order:
        if not _provider_has_key(provider):
            logger.info("[LLM] Skipping %s — no API key configured", provider)
            continue

        fn = PROVIDERS[provider]
        try:
            result = fn(prompt, temperature)
            if _is_valid_llm_output(result):
                cache.set(prompt, f"llm:{provider}", result)
                logger.info("[LLM] Success | provider=%s | len=%d", provider, len(result))
                return result
            else:
                logger.warning("[LLM] Invalid output from %s (len=%d)", provider, len(result))
                errors.append(f"{provider}: invalid output")
        except Exception as exc:
            logger.error("[LLM] %s failed: %s", provider, exc)
            errors.append(f"{provider}: {exc}")

    raise RuntimeError(f"All LLM providers failed: {'; '.join(errors)}")


def call_llm_with_fallback(prompt: str, temperature: float = 0.7,
                            fallback_text: str = "{}") -> str:
    """Call LLM with a fallback text if all providers fail."""
    try:
        return call_llm(prompt, temperature)
    except Exception as exc:
        logger.error("[LLM] All providers failed, returning fallback: %s", exc)
        return fallback_text
