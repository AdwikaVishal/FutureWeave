"""
Synthesis Agent — one LLM call for regret + letters + comparator.

This replaces 7 separate LLM calls (3 regret + 3 letter + 1 comparator)
with a single batched call. Falls back to deterministic outputs if the
LLM is unavailable or quota is exhausted.
"""
import json
import logging
import os

from llm_client import call_llm
from llm_cache import get_cache
from quota_manager import get_quota_manager
from input_validator import safe_template_substitute
from domains import get_regrets, get_letter, get_domain, get_archetype_label

logger = logging.getLogger(__name__)

# Module-level store — populated by batch_synthesis(), read by agents
_synthesis_store: dict = {}

# Timeline personality descriptions injected into every prompt
TIMELINE_PERSONALITIES = {
    "Timeline A": "The Settler — chose security and roots. Optimised for stability, relationships, and quality of life. Income grew slowly. Stress stayed low. Happiness came from belonging, not achievement.",
    "Timeline B": "The Climber — disciplined, strategic ambition. Took calculated risks, invested in skills, sought promotions through merit. Career_growth was the lead node. Balanced ambition with stability.",
    "Timeline C": "The Gambler — bet big and moved fast. Job-hopped, chased equity, launched side projects. Income was volatile. Stress spiked hard by Year3. Health and relationships paid the price. Opportunity was always the highest node.",
}


def get_synthesis_store() -> dict:
    return _synthesis_store


def _load_prompt(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
    with open(path) as f:
        return f.read()


# ── Score summary builder ─────────────────────────────────────────────────────

def _build_tl_summary(timelines: dict) -> dict:
    """Extract narratives + causal scores for each timeline."""
    tl_summary = {}
    for tl_key, tl_data in timelines.items():
        if tl_key.startswith("_"):
            continue
        causal = tl_data.get("_causal", {})
        narratives = {yr: tl_data.get(yr, "") for yr in ["Year1", "Year3", "Year5", "Year10"]}
        tl_summary[tl_key] = {
            "personality": TIMELINE_PERSONALITIES.get(tl_key, ""),
            "narratives": narratives,
            "causal_scores": causal,
        }
    return tl_summary


def _score_fingerprint(tl_summary: dict) -> str:
    """Stable hash of actual score values — ensures different simulations get different cache keys."""
    fingerprint = {}
    for tl_key, data in tl_summary.items():
        causal = data.get("causal_scores", {})
        fingerprint[tl_key] = {
            yr: {node: scores.get(node, 0) for node in ["income", "happiness", "stress"]}
            for yr, scores in causal.items()
        }
    return json.dumps(fingerprint, sort_keys=True)


# ── Deterministic fallbacks — distinct per timeline ──────────────────────────

_PERSONALITY_FALLBACKS = {}  # Deprecated — use domain-specific templates from domains.py


def _fallback_regret(tl_key: str, timeline: dict, domain_id: str = "career", archetype_key: str = "B") -> dict:
    """Distinct deterministic regret per timeline + domain.
    Uses domain-specific templates from domains.py."""
    return get_regrets(domain_id, archetype_key)


def _fallback_letter(tl_key: str, timeline: dict, regret: dict, domain_id: str = "career", archetype_key: str = "B") -> str:
    """Distinct deterministic letter per timeline + domain.
    Uses domain-specific templates from domains.py."""
    letter_template = get_letter(domain_id, archetype_key)
    causal = timeline.get("_causal", {})
    y10 = causal.get("Year10", {})
    income_score = y10.get("income", 50)
    happiness = y10.get("happiness", 50)

    opp = regret.get("lost_opportunity", "other paths")
    cost = regret.get("emotional_cost", "the weight of your choices")

    return (
        f"Dear you,\n\n"
        f"{letter_template}\n\n"
        f"I thought about {opp} more than I expected. "
        f"And {cost} — that stayed with me.\n\n"
        f"You'll be okay.\n\n"
        f"— You, ten years from now\n\n"
        f"Year 10 score: {income_score}/100. Happiness: {happiness}/100."
    )


def _fallback_comparison(timelines: dict) -> dict:
    """Deterministic comparison using actual score differences.
    
    Returns per-timeline score entries (consumed by _build_recommendation)
    PLUS human-readable text fields prefixed with _ to avoid iteration issues.
    """
    tl_keys = [k for k in timelines if not k.startswith("_")]
    scores = {}
    for tl_key in tl_keys:
        tl = timelines[tl_key]
        causal = tl.get("_causal", {})
        y10 = causal.get("Year10", {})
        scores[tl_key] = y10

    result = {}

    # Per-timeline score entries (consumed by _build_recommendation)
    for tl_key in tl_keys:
        y10 = scores.get(tl_key, {})
        result[tl_key] = {
            "overall_score": y10.get("happiness", 50),
            "happiness_score": y10.get("happiness", 50),
            "income_score": y10.get("income", 50),
            "stress_score": y10.get("stress", 50),
            "career_growth": y10.get("career_growth", 50),
        }

    has_scores = any(scores.values())

    if not has_scores:
        result["common_patterns"] = "All paths share the same starting conditions and economic environment."
        result["key_differences"] = "The timelines diverge in risk tolerance and career pace."
        result["hinge_point"] = "The decision itself — each path reflects a different relationship with risk."
        return result

    def best(node):
        return max(scores, key=lambda k: scores[k].get(node, 0)) if scores else "Timeline B"

    def worst(node):
        return min(scores, key=lambda k: scores[k].get(node, 0)) if scores else "Timeline B"

    best_income = best("income")
    best_happy = best("happiness")
    worst_stress = worst("stress")
    best_health = best("health")

    income_vals = {k: scores[k].get("income", 50) for k in tl_keys}
    happy_vals = {k: scores[k].get("happiness", 50) for k in tl_keys}
    stress_vals = {k: scores[k].get("stress", 50) for k in tl_keys}

    result["common_patterns"] = (
        f"All three paths start from the same decision and economic conditions. "
        f"Happiness tracks income closely in Years 1–3, then diverges as stress compounds. "
        f"Relationships are the most stable node across all timelines."
    )
    result["key_differences"] = (
        f"{best_income} produces the highest income by Year 10 "
        f"(score {income_vals.get(best_income, '?')}/100) "
        f"but {worst_stress} carries the lowest stress "
        f"(score {stress_vals.get(worst_stress, '?')}/100). "
        f"{best_happy} ends with the highest happiness ({happy_vals.get(best_happy, '?')}/100), "
        f"which is not always the highest-income path."
    )
    result["hinge_point"] = (
        f"The divergence point is Year 3 — where early career stress either compounds "
        f"into health decline ({max(tl_keys, key=lambda k: scores[k].get('stress', 0))} path) "
        f"or stabilises into sustainable growth. "
        f"Stress at Year 3 is the single strongest predictor of Year 10 happiness."
    )
    return result


# ── Synthesis completeness repair ────────────────────────────────────────────

def _ensure_complete_synthesis(result: dict, timelines: dict) -> dict:
    """
    Guarantee every timeline has regret + letter in the LLM result.
    Fills any missing or empty entries with distinct deterministic content
    so the frontend never shows blank or identical fallback text.
    Domain-aware: uses domain-specific templates.
    """
    tl_keys = [k for k in timelines if not k.startswith("_")]

    # Extract domain from timeline metadata
    domain_id = "career"
    for tl_key in tl_keys:
        tl = timelines.get(tl_key, {})
        dt = tl.get("_decision_type", "")
        if dt:
            domain_id = get_domain(dt).value
            break

    # Ensure top-level keys exist
    result.setdefault("regrets", {})
    result.setdefault("letters", {})
    result.setdefault("comparison", {})

    for tl_key in tl_keys:
        tl = timelines.get(tl_key, {})
        arch_key = tl_key[-1]  # "A", "B", "C"

        # ── Regret ──
        regret = result["regrets"].get(tl_key)
        if not regret or not isinstance(regret, dict):
            logger.warning("[Synthesis] Missing regret for %s — filling with deterministic", tl_key)
            regret = _fallback_regret(tl_key, tl, domain_id, arch_key)
            result["regrets"][tl_key] = regret
        else:
            # Patch any missing sub-fields
            fb_regret = _fallback_regret(tl_key, tl, domain_id, arch_key)
            for field in ("lost_opportunity", "missed_identity", "emotional_cost"):
                if not result["regrets"][tl_key].get(field):
                    result["regrets"][tl_key][field] = fb_regret[field]

        # ── Letter ──
        letter = result["letters"].get(tl_key)
        if not letter or not isinstance(letter, str) or len(letter.strip()) < 20:
            logger.warning("[Synthesis] Missing/short letter for %s — filling with deterministic", tl_key)
            result["letters"][tl_key] = _fallback_letter(tl_key, tl, result["regrets"][tl_key], domain_id, arch_key)

    # ── Comparison ──
    comp = result.get("comparison", {})
    for field in ("common_patterns", "key_differences", "hinge_point"):
        if not isinstance(comp.get(field), str):
            fb = _fallback_comparison(timelines)
            val = fb.get(field)
            if isinstance(val, str):
                result["comparison"][field] = val

    return result


# ── Batched synthesis ─────────────────────────────────────────────────────────

def batch_synthesis(timelines: dict, decision: str, context: dict) -> dict:
    """
    Run one LLM call to produce regrets + letters + comparison for all timelines.
    Cache key includes actual score values so different simulations never collide.
    """
    global _synthesis_store

    cache = get_cache()
    qm = get_quota_manager()

    tl_summary = _build_tl_summary(timelines)

    # Cache key includes actual score fingerprint — prevents cross-simulation collisions
    cache_key = cache.make_key(
        "synthesis_v2",
        decision,
        json.dumps(context, sort_keys=True, default=str),
        _score_fingerprint(tl_summary),
    )

    cached = cache.get(cache_key, model="batch_synthesis")
    if cached is not None:
        logger.info("[Synthesis] Cache hit — skipping LLM call")
        _synthesis_store = cached
        return cached

    if not qm.should_use_llm("synthesis"):
        logger.info("[Synthesis] Quota mode '%s' — deterministic fallback", qm.mode)
        store = _build_fallback_store(timelines, decision)
        _synthesis_store = store
        return store

    # Build prompt with personalities + actual scores injected
    template = _load_prompt("batch_synthesis_prompt.txt")
    prompt = safe_template_substitute(
        template,
        decision=decision,
        age=str(context.get("age", "unknown")),
        timelines_json=json.dumps(tl_summary, indent=2, default=str),
    )

    try:
        raw = call_llm(prompt, temperature=0.75)
        qm.record_call()
        parsed = json.loads(raw)

        for key in ("regrets", "letters", "comparison"):
            if key not in parsed:
                raise ValueError(f"Missing key in synthesis response: {key}")

        # Repair any missing per-timeline entries before caching
        parsed = _ensure_complete_synthesis(parsed, timelines)

        cache.set(cache_key, model="batch_synthesis", response=parsed)
        _synthesis_store = parsed
        logger.info("[Synthesis] Batched LLM call succeeded")
        return parsed

    except Exception as exc:
        qm.record_error(is_rate_limit="rate" in str(exc).lower() or "429" in str(exc))
        logger.warning("[Synthesis] LLM failed: %s — deterministic fallback", exc)
        store = _build_fallback_store(timelines, decision)
        _synthesis_store = store
        return store


def _build_fallback_store(timelines: dict, decision: str) -> dict:
    regrets = {}
    letters = {}
    tl_keys = [k for k in timelines if not k.startswith("_")]

    # Extract domain from timeline metadata
    domain_id = "career"
    for tl_key in tl_keys:
        tl = timelines.get(tl_key, {})
        dt = tl.get("_decision_type", "")
        if dt:
            domain_id = get_domain(dt).value
            break

    for tl_key in tl_keys:
        tl = timelines[tl_key]
        arch_key = tl_key[-1]
        regret = _fallback_regret(tl_key, tl, domain_id, arch_key)
        regrets[tl_key] = regret
        letters[tl_key] = _fallback_letter(tl_key, tl, regret, domain_id, arch_key)

    comparison = _fallback_comparison(timelines)
    return {"regrets": regrets, "letters": letters, "comparison": comparison}
