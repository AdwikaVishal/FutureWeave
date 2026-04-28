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

logger = logging.getLogger(__name__)

# Module-level store — populated by batch_synthesis(), read by agents
_synthesis_store: dict = {}

# Timeline personality descriptions injected into every prompt
TIMELINE_PERSONALITIES = {
    "Timeline A": "Conservative/safe path — steady income, low risk, moderate career growth, good work-life balance, stable relationships. This person chose security over ambition.",
    "Timeline B": "Balanced path — moderate risk-taking, steady career progression, some stress but manageable. This person balanced ambition with stability.",
    "Timeline C": "High-risk/high-reward path — aggressive career moves, high stress, potential for large income gains or burnout. This person bet on themselves hard.",
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

_PERSONALITY_FALLBACKS = {
    "Timeline A": {
        "regret": {
            "lost_opportunity": "The startup you never launched — you had the idea but chose the safe job.",
            "missed_identity": "A version of yourself who took the leap and built something from scratch.",
            "emotional_cost": "The Sunday-evening feeling that you played it too safe.",
        },
        "letter_opening": (
            "You chose stability, and it gave you exactly what it promised — "
            "a steady income, predictable weekends, and a life that looks fine from the outside."
        ),
        "letter_hard": "What was harder than expected: watching peers who took risks pull ahead by Year 5.",
        "letter_advice": "Don't confuse comfort with contentment. They're not the same thing.",
    },
    "Timeline B": {
        "regret": {
            "lost_opportunity": "The chance to go all-in on a high-growth opportunity you half-committed to.",
            "missed_identity": "A version of yourself who was either more daring or more grounded — not perpetually in between.",
            "emotional_cost": "The nagging sense that you were always hedging, never fully present in either direction.",
        },
        "letter_opening": (
            "You walked the middle path — not the safest, not the boldest. "
            "Most days that felt wise. Some days it felt like cowardice."
        ),
        "letter_hard": "What was harder than expected: the middle path has no community. Risk-takers bond over war stories. Safe players bond over stability. You were neither.",
        "letter_advice": "Pick a lane earlier. The middle is lonelier than it looks.",
    },
    "Timeline C": {
        "regret": {
            "lost_opportunity": "The relationships you let atrophy while chasing the next milestone.",
            "missed_identity": "A version of yourself who was present — at dinners, at weekends, in conversations.",
            "emotional_cost": "The realisation at Year 7 that your income had tripled but you had no one to celebrate with.",
        },
        "letter_opening": (
            "You went all in. The income is real, the title is real, the exhaustion is real. "
            "You got what you wanted — and discovered it wasn't quite what you needed."
        ),
        "letter_hard": "What was harder than expected: high income doesn't fix the 2am anxiety. It just makes the anxiety more expensive.",
        "letter_advice": "Build the income. But schedule the relationships like you schedule the meetings. They don't maintain themselves.",
    },
}


def _fallback_regret(tl_key: str, timeline: dict) -> dict:
    """Distinct deterministic regret per timeline personality."""
    fb = _PERSONALITY_FALLBACKS.get(tl_key)
    if fb:
        return dict(fb["regret"])

    # Generic fallback for unexpected keys
    causal = timeline.get("_causal", {})
    y10 = causal.get("Year10", {})
    income = y10.get("income", 50)
    stress = y10.get("stress", 50)
    if stress > 65:
        return {
            "lost_opportunity": "A less demanding role with better work-life balance.",
            "missed_identity": "A version of yourself with more time for personal growth.",
            "emotional_cost": "The recurring tension between career ambition and personal wellbeing.",
        }
    if income > 70:
        return {
            "lost_opportunity": "Deeper relationships sacrificed for career acceleration.",
            "missed_identity": "A version who was present, not just successful.",
            "emotional_cost": "The gap between external success and internal fulfilment.",
        }
    return {
        "lost_opportunity": "An alternative path with higher risk and potentially higher reward.",
        "missed_identity": "A version who pushed harder earlier in their career.",
        "emotional_cost": "The occasional wonder about roads not taken.",
    }


def _fallback_letter(tl_key: str, timeline: dict, regret: dict) -> str:
    """Distinct deterministic letter per timeline personality."""
    fb = _PERSONALITY_FALLBACKS.get(tl_key)
    causal = timeline.get("_causal", {})
    y10 = causal.get("Year10", {})
    income_score = y10.get("income", 50)
    happiness = y10.get("happiness", 50)

    if fb:
        opening = fb["letter_opening"]
        hard = fb["letter_hard"]
        advice = fb["letter_advice"]
    else:
        years = [v for k, v in timeline.items() if k.startswith("Year") and isinstance(v, str)]
        opening = years[-1] if years else "Your life has unfolded in ways you didn't expect."
        hard = "The early years were harder than the numbers suggested."
        advice = "Make the decision you can explain to yourself five years from now."

    opp = regret.get("lost_opportunity", "other paths")
    cost = regret.get("emotional_cost", "the weight of your choices")

    return (
        f"Dear you,\n\n"
        f"{opening}\n\n"
        f"I thought about {opp} more than I expected. "
        f"And {cost} — that stayed with me.\n\n"
        f"{hard}\n\n"
        f"{advice}\n\n"
        f"Income score at Year 10: {income_score}/100. Happiness: {happiness}/100. "
        f"The gap between those two numbers is the story of this path.\n\n"
        f"You'll be okay.\n\n"
        f"— You, ten years from now"
    )


def _fallback_comparison(timelines: dict) -> dict:
    """Deterministic comparison using actual score differences."""
    tl_keys = [k for k in timelines if not k.startswith("_")]
    scores = {}
    for tl_key in tl_keys:
        tl = timelines[tl_key]
        causal = tl.get("_causal", {})
        y10 = causal.get("Year10", {})
        scores[tl_key] = y10

    if not any(scores.values()):
        return {
            "common_patterns": "All paths share the same starting conditions and economic environment.",
            "key_differences": "The timelines diverge in risk tolerance and career pace.",
            "hinge_point": "The decision itself — each path reflects a different relationship with risk.",
        }

    # Find highest/lowest on key nodes
    def best(node):
        return max(scores, key=lambda k: scores[k].get(node, 0)) if scores else "Timeline B"

    def worst(node):
        return min(scores, key=lambda k: scores[k].get(node, 0)) if scores else "Timeline B"

    best_income = best("income")
    best_happy = best("happiness")
    worst_stress = worst("stress")  # lowest stress = best stress outcome
    best_health = best("health")

    income_vals = {k: scores[k].get("income", 50) for k in tl_keys}
    happy_vals = {k: scores[k].get("happiness", 50) for k in tl_keys}
    stress_vals = {k: scores[k].get("stress", 50) for k in tl_keys}

    return {
        "common_patterns": (
            f"All three paths start from the same decision and economic conditions. "
            f"Happiness tracks income closely in Years 1–3, then diverges as stress compounds. "
            f"Relationships are the most stable node across all timelines."
        ),
        "key_differences": (
            f"{best_income} produces the highest income by Year 10 "
            f"(score {income_vals.get(best_income, '?')}/100) "
            f"but {worst_stress} carries the lowest stress "
            f"(score {stress_vals.get(worst_stress, '?')}/100). "
            f"{best_happy} ends with the highest happiness ({happy_vals.get(best_happy, '?')}/100), "
            f"which is not always the highest-income path."
        ),
        "hinge_point": (
            f"The divergence point is Year 3 — where early career stress either compounds "
            f"into health decline ({max(tl_keys, key=lambda k: scores[k].get('stress', 0))} path) "
            f"or stabilises into sustainable growth. "
            f"Stress at Year 3 is the single strongest predictor of Year 10 happiness."
        ),
    }


# ── Synthesis completeness repair ────────────────────────────────────────────

def _ensure_complete_synthesis(result: dict, timelines: dict) -> dict:
    """
    Guarantee every timeline has regret + letter in the LLM result.
    Fills any missing or empty entries with distinct deterministic content
    so the frontend never shows blank or identical fallback text.
    """
    tl_keys = [k for k in timelines if not k.startswith("_")]

    # Ensure top-level keys exist
    result.setdefault("regrets", {})
    result.setdefault("letters", {})
    result.setdefault("comparison", {})

    for tl_key in tl_keys:
        tl = timelines.get(tl_key, {})

        # ── Regret ──
        regret = result["regrets"].get(tl_key)
        if not regret or not isinstance(regret, dict):
            logger.warning("[Synthesis] Missing regret for %s — filling with deterministic", tl_key)
            regret = _fallback_regret(tl_key, tl)
            result["regrets"][tl_key] = regret
        else:
            # Patch any missing sub-fields
            fb_regret = _fallback_regret(tl_key, tl)
            for field in ("lost_opportunity", "missed_identity", "emotional_cost"):
                if not result["regrets"][tl_key].get(field):
                    result["regrets"][tl_key][field] = fb_regret[field]

        # ── Letter ──
        letter = result["letters"].get(tl_key)
        if not letter or not isinstance(letter, str) or len(letter.strip()) < 20:
            logger.warning("[Synthesis] Missing/short letter for %s — filling with deterministic", tl_key)
            result["letters"][tl_key] = _fallback_letter(tl_key, tl, result["regrets"][tl_key])

    # ── Comparison ──
    comp = result.get("comparison", {})
    for field in ("common_patterns", "key_differences", "hinge_point"):
        if not comp.get(field):
            fb = _fallback_comparison(timelines)
            result["comparison"][field] = fb[field]

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
        json.dumps(context, sort_keys=True),
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
    prompt = (
        template
        .replace("{decision}", decision)
        .replace("{age}", str(context.get("age", "unknown")))
        .replace("{timelines_json}", json.dumps(tl_summary, indent=2))
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

    for tl_key in tl_keys:
        tl = timelines[tl_key]
        regret = _fallback_regret(tl_key, tl)
        regrets[tl_key] = regret
        letters[tl_key] = _fallback_letter(tl_key, tl, regret)

    comparison = _fallback_comparison(timelines)
    return {"regrets": regrets, "letters": letters, "comparison": comparison}
