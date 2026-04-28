import os
import re
import time
from litellm import completion
from dotenv import load_dotenv

# Load env variables FIRST
load_dotenv()

# ✅ Correct Gemini import
import google.generativeai as google_genai

from llm_cache import get_cache
from quota_manager import get_quota_manager

_cache = get_cache()
_quota = get_quota_manager()

# ✅ Configure Gemini
google_genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
_GEMINI_MODEL = "gemini-1.5-flash"

# Groq fallback config
_GROQ_MODEL = "groq/llama-3.3-70b-versatile"
_MAX_RETRIES = 3
_RETRY_BASE_SEC = 3.0


def clean_json(raw: str, verbose: bool = False) -> str:
    if verbose:
        print(f"[DEBUG] Raw LLM response:\n{raw[:500]}\n")

    raw = re.sub(r'```json\s*', '', raw)
    raw = re.sub(r'```\s*', '', raw)

    start = raw.find('{')
    end = raw.rfind('}')

    if start != -1 and end != -1:
        raw = raw[start:end + 1]

    return raw.strip()


def _is_rate_limit(err: Exception) -> bool:
    s = str(err).lower()
    return "429" in s or "rate limit" in s


def _retry_delay(err_str: str, attempt: int) -> float:
    return _RETRY_BASE_SEC * (2 ** attempt)


# ✅ Gemini call (fixed)
def call_gemini(prompt: str, temperature: float = 0.7) -> str:
    print(f"[LLM] >>> Calling Gemini")

    response = google_genai.generate_content(
        model=_GEMINI_MODEL,
        contents=prompt,
        generation_config={"temperature": temperature},
    )

    raw = response.text
    print(f"[LLM] <<< Gemini response ({len(raw)} chars)")

    return clean_json(raw)


# ✅ Groq fallback
def call_groq(prompt: str, temperature: float = 0.7) -> str:
    last_err = None

    for attempt in range(_MAX_RETRIES):
        try:
            print(f"[LLM] >>> Groq attempt {attempt+1}")

            response = completion(
                model=_GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )

            raw = response.choices[0].message.content
            return clean_json(raw)

        except Exception as err:
            last_err = err
            print(f"[LLM ERROR] {err}")

            if _is_rate_limit(err) and attempt < _MAX_RETRIES - 1:
                time.sleep(_retry_delay(str(err), attempt))
                continue

            break

    raise last_err


def _is_valid_llm_output(text: str) -> bool:
    if not text or len(text.strip()) < 10:
        return False

    if text.startswith('{') and not text.endswith('}'):
        return False

    return True


# ✅ Main function
def call_llm(prompt: str, temperature: float = 0.7) -> str:
    print(f"[LLM] call_llm | prompt_len={len(prompt)}")

    # Cache
    cached = _cache.get(prompt, _GEMINI_MODEL)
    if cached:
        print("[LLM] Cache hit")
        return cached

    # Quota check
    if _quota.state["mode"] == "offline":
        raise Exception("LLM disabled (offline mode)")

    # Try Gemini
    try:
        result = call_gemini(prompt, temperature)

        if _is_valid_llm_output(result):
            _cache.set(prompt, _GEMINI_MODEL, result)
            _quota.check_and_update(success=True)
            return result

    except Exception as err:
        print(f"[LLM] Gemini failed: {err}")
        _quota.check_and_update(success=False)

    # Fallback to Groq
    print("[LLM] Falling back to Groq")

    result = call_groq(prompt, temperature)

    if not _is_valid_llm_output(result):
        raise Exception("Groq output invalid")

    _cache.set(prompt, "groq", result)
    _quota.check_and_update(success=True)

    return result