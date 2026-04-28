import os
import re
import time
from litellm import completion
from dotenv import load_dotenv

# Load .env BEFORE reading any env vars
load_dotenv()

from google import genai as google_genai
from google.genai import errors as genai_errors

from llm_cache import get_cache
from quota_manager import get_quota_manager

_cache = get_cache()
_quota = get_quota_manager()

# Configure Gemini — key is now available because load_dotenv() ran first
_gemini_client = google_genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
_GEMINI_MODEL = "gemini-2.5-flash"

# Groq fallback config
_GROQ_MODEL     = "groq/llama-3.3-70b-versatile"
_MAX_RETRIES    = 3
_RETRY_BASE_SEC = 3.0


def clean_json(raw: str, verbose: bool = False) -> str:
    """Extract JSON from LLM response, handling markdown and extra text."""
    if verbose:
        print(f"[DEBUG] Raw LLM response (first 500 chars):\n{raw[:500]}\n")
    raw = re.sub(r'```json\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw)
    start = raw.find('{')
    end = raw.rfind('}')
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    cleaned = raw.strip()
    if verbose:
        print(f"[DEBUG] Cleaned JSON (first 500 chars):\n{cleaned[:500]}\n")
    return cleaned


def _is_rate_limit(err: Exception) -> bool:
    s = str(err).lower()
    return (
        "429" in s
        or "rate limit" in s
        or "ratelimit" in s
        or "tokens per minute" in s
        or "resource_exhausted" in s
    )


def _retry_delay(err_str: str, attempt: int) -> float:
    match = re.search(r"retry.*?(\d+)s", err_str, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1.0
    return _RETRY_BASE_SEC * (2 ** attempt)


def call_gemini(prompt: str, temperature: float = 0.7) -> str:
    """Call Gemini via the new google-genai SDK and return cleaned response."""
    print(f"[LLM] >>> Calling {_GEMINI_MODEL}")
    response = _gemini_client.models.generate_content(
        model=_GEMINI_MODEL,
        contents=prompt,
        config={"temperature": temperature},
    )
    raw = response.text
    print(f"[LLM] <<< Gemini response received ({len(raw)} chars)")
    return clean_json(raw, verbose=False)


def call_groq(prompt: str, temperature: float = 0.7) -> str:
    """Call Groq llama-3.3-70b as fallback with retry on rate limit."""
    last_err = None
    for attempt in range(_MAX_RETRIES):
        try:
            print(f"[LLM] >>> Calling Groq {_GROQ_MODEL} (attempt {attempt + 1})")
            response = completion(
                model=_GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            raw = response.choices[0].message.content
            print(f"[LLM] <<< Groq response received ({len(raw)} chars)")
            return clean_json(raw, verbose=False)
        except Exception as err:
            last_err = err
            print(f"[LLM ERROR] Groq attempt {attempt + 1} failed: {str(err)[:200]}")
            if _is_rate_limit(err) and attempt < _MAX_RETRIES - 1:
                wait = _retry_delay(str(err), attempt)
                print(f"[LLM] Rate limit — waiting {wait:.1f}s before retry...")
                time.sleep(wait)
                continue
            break
    raise last_err


def _is_valid_llm_output(text: str) -> bool:
    """
    Reject responses that are obviously malformed.
    Score-degenerate checks only apply to causal-score payloads (contain "income").
    """
    if not text or len(text.strip()) < 10:
        return False

    stripped = text.strip()

    # Only apply score checks when this looks like a causal scores response
    if '"income"' in stripped:
        if stripped.count('"income": 0') > 2 or stripped.count('"income":0') > 2:
            print("[LLM] ⚠ Degenerate income=0 scores detected — triggering fallback")
            return False
        if stripped.count('"stress": 0') > 2 or stripped.count('"stress":0') > 2:
            print("[LLM] ⚠ Degenerate stress=0 scores detected — triggering fallback")
            return False

    # Reject clearly truncated JSON
    if stripped.startswith('{') and not stripped.endswith('}'):
        print("[LLM] ⚠ Truncated JSON (no closing brace) — triggering fallback")
        return False

    return True


def call_llm(prompt: str, model: str = None, temperature: float = 0.7) -> str:
    """
    Primary: Gemini 2.5 Flash.
    Fallback: Groq llama-3.3-70b if Gemini fails OR returns invalid/degenerate output.
    """
    print(f"[LLM] call_llm() invoked | prompt_len={len(prompt)}")

    # 1. Check cache
    cached = _cache.get(prompt, _GEMINI_MODEL)
    if cached:
        print("[LLM] Cache hit — returning cached response")
        return cached

    print("[LLM] Cache miss — proceeding to live call")

    # 2. Check quota mode
    mode = _quota.state["mode"]
    print(f"[LLM] Quota mode: {mode} | calls_today: {_quota.state['calls_today']}")
    if mode == "offline":
        raise Exception("[LLM] Offline mode — no LLM calls allowed.")

    # 3. Try Gemini first
    gemini_err = None
    try:
        result = call_gemini(prompt, temperature)
        if _is_valid_llm_output(result):
            _cache.set(prompt, _GEMINI_MODEL, result)
            _quota.check_and_update(success=True)
            print("[LLM] Primary call succeeded ✓ (Gemini)")
            return result
        else:
            gemini_err = "Response failed content validation (degenerate/truncated output)"
            print(f"[LLM] Gemini output invalid: {gemini_err}")
            _quota.check_and_update(success=False)
    except Exception as err:
        gemini_err = err
        print(f"[LLM] Gemini failed, falling back to Groq: {err}")
        _quota.check_and_update(success=False)

    # 4. Fallback to Groq
    print("[LLM] 🔄 FALLBACK to Groq — Gemini failed or returned invalid output")
    try:
        result = call_groq(prompt, temperature)
        if not _is_valid_llm_output(result):
            raise Exception("Groq response also failed content validation")
        _cache.set(prompt, "groq", result)
        _quota.check_and_update(success=True)
        print("[LLM] Groq fallback succeeded ✓")
        return result
    except Exception as groq_err:
        print(f"[LLM ERROR] Groq also failed: {groq_err}")
        _quota.check_and_update(success=False)
        raise Exception(f"Both providers failed — Gemini: {gemini_err} | Groq: {groq_err}")
