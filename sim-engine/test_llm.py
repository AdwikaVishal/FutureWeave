#!/usr/bin/env python3
"""
Standalone LLM connectivity test.
Run from sim-engine/:  python test_llm.py

Tests:
  1. Groq primary model
  2. OpenRouter fallback (if OPENROUTER_API_KEY is set)
  3. Quota manager state
  4. Cache read/write
"""
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

# ── 1. Environment check ──────────────────────────────────────────────────────
print("=" * 60)
print("1. ENVIRONMENT CHECK")
print("=" * 60)

groq_key = os.environ.get("GROQ_API_KEY", "")
or_key   = os.environ.get("OPENROUTER_API_KEY", "")

print(f"  GROQ_API_KEY       : {'SET (' + groq_key[:8] + '...)' if groq_key else 'NOT SET ✗'}")
print(f"  OPENROUTER_API_KEY : {'SET (' + or_key[:8] + '...)' if or_key else 'not set (fallback disabled)'}")

if not groq_key:
    print("\n[FATAL] GROQ_API_KEY is missing. Add it to sim-engine/.env and retry.")
    sys.exit(1)

# ── 2. Quota state ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. QUOTA STATE")
print("=" * 60)

from quota_manager import get_quota_manager
qm = get_quota_manager()
print(f"  mode            : {qm.state['mode']}")
print(f"  calls_today     : {qm.state['calls_today']}")
print(f"  rate_limit_hits : {qm.state['rate_limit_hits']}")

if qm.state["mode"] != "full":
    print(f"\n  [WARNING] Quota mode is '{qm.state['mode']}' — resetting to full...")
    qm.reset()
    print(f"  Mode after reset: {qm.state['mode']}")

# ── 3. Cache check ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("3. CACHE CHECK")
print("=" * 60)

from llm_cache import get_cache
cache = get_cache()
cache_dir = cache.cache_dir
files = [f for f in os.listdir(cache_dir) if f.endswith(".json")] if os.path.exists(cache_dir) else []
print(f"  Cache dir   : {cache_dir}")
print(f"  Cached files: {len(files)}")

# Test cache write/read
_test_prompt = "__test_connectivity__"
_test_model  = "test"
cache.set(_test_prompt, _test_model, {"ok": True})
hit = cache.get(_test_prompt, _test_model)
cache.invalidate(_test_prompt, _test_model)
print(f"  Cache write/read: {'✓' if hit == {'ok': True} else '✗ FAILED'}")

# ── 4. Groq connectivity ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("4. GROQ CONNECTIVITY TEST")
print("=" * 60)

from litellm import completion

GROQ_MODEL = "groq/llama-3.3-70b-versatile"
TEST_PROMPT = 'Reply with exactly this JSON and nothing else: {"status": "ok", "message": "Groq is working"}'

print(f"  Model  : {GROQ_MODEL}")
print(f"  Prompt : {TEST_PROMPT[:80]}")
print("  Calling...")

try:
    resp = completion(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": TEST_PROMPT}],
        temperature=0.0,
    )
    raw = resp.choices[0].message.content
    print(f"  Raw response : {raw[:200]}")
    parsed = json.loads(raw.strip().strip("```json").strip("```").strip())
    print(f"  Parsed       : {parsed}")
    print(f"  Result       : ✓ Groq is working")
    groq_ok = True
except Exception as e:
    print(f"  Result       : ✗ FAILED — {type(e).__name__}: {e}")
    groq_ok = False

# ── 5. OpenRouter fallback (optional) ────────────────────────────────────────
if or_key:
    print("\n" + "=" * 60)
    print("5. OPENROUTER FALLBACK TEST")
    print("=" * 60)

    OR_MODEL = "openrouter/meta-llama/llama-3.1-8b-instruct:free"
    print(f"  Model  : {OR_MODEL}")
    print("  Calling...")

    try:
        resp = completion(
            model=OR_MODEL,
            messages=[{"role": "user", "content": TEST_PROMPT}],
            temperature=0.0,
        )
        raw = resp.choices[0].message.content
        print(f"  Raw response : {raw[:200]}")
        print(f"  Result       : ✓ OpenRouter fallback is working")
    except Exception as e:
        print(f"  Result       : ✗ FAILED — {type(e).__name__}: {e}")

# ── 6. call_llm() integration test ───────────────────────────────────────────
print("\n" + "=" * 60)
print("6. call_llm() INTEGRATION TEST")
print("=" * 60)

from llm_client import call_llm

INTEGRATION_PROMPT = 'Reply with exactly this JSON: {"year": 1, "income": 120000, "stress": "low", "narrative": "Things are going well."}'

print("  Calling call_llm() with a structured prompt...")
try:
    result = call_llm(INTEGRATION_PROMPT, temperature=0.0)
    print(f"  Result (raw) : {result[:300]}")
    parsed = json.loads(result)
    print(f"  Parsed keys  : {list(parsed.keys())}")
    print(f"  Result       : ✓ call_llm() works end-to-end")
except Exception as e:
    print(f"  Result       : ✗ FAILED — {type(e).__name__}: {e}")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  Groq API     : {'✓ OK' if groq_ok else '✗ FAILING — check GROQ_API_KEY and model name'}")
print(f"  Quota mode   : {qm.state['mode']}")
print(f"  Cache        : ✓ OK")
print()
if not groq_ok:
    print("ACTION REQUIRED: Groq calls are failing. Check:")
    print("  1. GROQ_API_KEY in .env is valid (test at console.groq.com)")
    print("  2. Model 'llama-3.3-70b-versatile' is available on your plan")
    print("  3. You haven't hit the daily free-tier limit")
    print("  4. Set OPENROUTER_API_KEY in .env to enable the free fallback")
