"""
Timeline Agent — batched, cached, quota-aware.

LLM call budget per simulation:
  - 1 call  : batch_timeline_prompt  → all 3 timelines × 4 years at once
  - 0 calls : chaos is always deterministic (no LLM)
  - 0 calls : narratives are template-based (no LLM)
  Total: 1 LLM call for timeline generation (down from 12)

In low/offline mode the single timeline call is also skipped and
_causal_transition() produces all scores deterministically.

Caching: results are keyed by SHA-256(decision + context + grounding hash)
and stored on disk for 7 days.
"""
import json
import logging
import os
import random
from datetime import datetime

from llm_client import call_llm
from llm_cache import get_cache
from quota_manager import get_quota_manager
from decision_parser import parse_decision, format_options_for_prompt
from input_validator import safe_template_substitute
from domains import get_metrics_by_type, get_domain

logger = logging.getLogger(__name__)

# ── Grounding ─────────────────────────────────────────────────────────────────
try:
    from data_grounding import (
        get_grounding_data, build_score_anchors,
        score_to_lpa, compute_core_variables,
    )
    DATA_GROUNDING_AVAILABLE = True
except ImportError:
    DATA_GROUNDING_AVAILABLE = False
    logger.warning("[Timeline] data_grounding not available — using defaults")

# ── Constants ─────────────────────────────────────────────────────────────────
NODES = [
    "income", "career_growth", "stress",
    "health", "relationships", "happiness", "opportunity",
]
CAUSAL_EDGES = [
    ("career_growth", "income",        0.25),
    ("career_growth", "stress",        0.20),
    ("stress",        "health",       -0.30),
    ("health",        "happiness",     0.20),
    ("income",        "happiness",     0.15),
    ("relationships", "happiness",     0.20),
    ("opportunity",   "career_growth", 0.15),
]
YEARS      = ["Year1", "Year3", "Year5", "Year10"]
YEAR_GAPS  = {"Year1": 0, "Year3": 2, "Year5": 2, "Year10": 5}
TIMELINE_KEYS = ["Timeline A", "Timeline B", "Timeline C"]
TIMELINE_PERSONALITIES = {
    "Timeline A": (
        "The Settler: chooses security and roots. Optimises for stability, relationships, "
        "and quality of life over income. Stress stays low, relationships lead, "
        "happiness driven by health and belonging. Opportunities taken only when risk-free."
    ),
    "Timeline B": (
        "The Climber: disciplined, strategic ambition. Takes calculated risks, invests in skills, "
        "seeks promotions through merit. Income grows at market rate. Stress is moderate and managed. "
        "Career_growth is the lead node. Opportunities evaluated and selectively pursued."
    ),
    "Timeline C": (
        "The Gambler: bets big and moves fast. Job hops, launches side projects, chases equity. "
        "Income is volatile — high ceiling, real floor risk. Stress spikes sharply by Year3. "
        "Health and relationships decline by Year5. Opportunity is the highest node. "
        "Happiness at Year10 either leads or trails all timelines — never middle."
    ),
}

# Personality bias for deterministic fallback
# A=Settler: low stress bias, high relationships; B=Climber: career-forward; C=Gambler: volatile
_PERSONALITY_BIAS = {"A": -5, "B": +2, "C": +8}

# Per-node overrides applied in _deterministic_all_years for archetype fidelity
_PERSONALITY_NODE_BIAS = {
    "A": {"stress": -12, "relationships": +12, "opportunity": -8,  "career_growth": -5},
    "B": {"stress":  +2, "relationships":   0, "opportunity": +5,  "career_growth": +8},
    "C": {"stress": +18, "relationships": -10, "opportunity": +15, "career_growth": +6},
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_prompt(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", filename)
    with open(path) as f:
        return f.read()


def _clamp(val: float) -> int:
    return max(0, min(100, int(round(val))))


def _validate_year(raw: dict) -> dict:
    return {node: _clamp(raw.get(node, 50)) for node in NODES}


def _validate_causal_scores(all_causal: dict) -> dict:
    """
    Post-process all timeline causal scores:
    - Clamp to 0–100
    - Replace implausible zeros on income/stress with realistic minimums
    - If an entire timeline is missing, fill with deterministic fallback
    """
    for tl_key in TIMELINE_KEYS:
        if tl_key not in all_causal:
            logger.warning("[Timeline] %s missing from LLM output — will use deterministic", tl_key)
            continue
        for yr in YEARS:
            if yr not in all_causal[tl_key]:
                logger.warning("[Timeline] %s/%s missing — will be filled by transition", tl_key, yr)
                continue
            nodes = all_causal[tl_key][yr]
            for node in NODES:
                val = nodes.get(node, 50)
                if not isinstance(val, (int, float)) or val < 0 or val > 100:
                    logger.warning("[Timeline] Invalid %s=%s in %s/%s — clamping to 50", node, val, tl_key, yr)
                    nodes[node] = 50
                # Income should never collapse to 0 for a working professional.
                if node == "income" and nodes[node] < 5:
                    logger.warning("[Timeline] Degenerate income=%s in %s/%s — clamping to 5", nodes[node], tl_key, yr)
                    nodes[node] = 5
                # Stress of exactly 0 is unrealistic
                if node == "stress" and nodes[node] == 0:
                    nodes[node] = 20
    return all_causal


def _apply_chaos_deltas(scores: dict, chaos_events: list, year: str) -> dict:
    """Apply deterministic chaos deltas without crashing on malformed event payloads."""
    result = dict(scores)

    if isinstance(chaos_events, dict):
        chaos_events = chaos_events.get("events", []) or chaos_events.get("items", [])

    for event in chaos_events or []:
        if not isinstance(event, dict):
            logger.warning("[Timeline] Ignoring non-dict chaos event for %s: %r", year, event)
            continue

        event_year = event.get("year") or event.get("Year")
        if isinstance(event_year, int):
            event_year = f"Year{event_year}"

        if event_year != year:
            continue

        node_deltas = event.get("node_deltas") or event.get("impact", {})
        if not isinstance(node_deltas, dict):
            logger.warning("[Timeline] Invalid node_deltas for %s: %r", year, node_deltas)
            continue

        for node, delta in node_deltas.items():
            if node in result and isinstance(delta, (int, float)):
                new_val = result[node] + delta
                if node == "income" and new_val < 5:
                    logger.warning("[Timeline] Chaos would set income=%.1f — clamping to 5", new_val)
                    new_val = 5
                result[node] = _clamp(new_val)

    return result


def _score_to_lpa_safe(score: int, anchors: dict) -> float | None:
    entry = anchors.get("salary_entry_lpa")
    mid = anchors.get("salary_mid_lpa")
    senior = anchors.get("salary_senior_lpa")
    if entry and mid and senior:
        return score_to_lpa(score, entry, mid, senior)
    income_anchors = anchors.get("income_anchors")
    if income_anchors and isinstance(income_anchors, dict):
        pts = sorted(income_anchors.items())
        for i in range(len(pts) - 1):
            s0, v0 = pts[i]
            s1, v1 = pts[i + 1]
            if s0 <= score <= s1:
                t = (score - s0) / (s1 - s0)
                return round(v0 + t * (v1 - v0), 1)
        return pts[-1][1]
    return None


def _get_anchors(decision: str, context: dict) -> dict:
    use_grounding = os.environ.get("USE_DATA_GROUNDING", "true").lower() == "true"
    if DATA_GROUNDING_AVAILABLE and use_grounding:
        try:
            g       = get_grounding_data(decision, context)
            anchors = build_score_anchors(g)
            cvars   = compute_core_variables(g, context)
            anchors["_computed"]  = cvars
            anchors["_grounding"] = g
            anchors["prompt_block"] = anchors["prompt_block"] + "\n" + cvars["computed_block"]
            return anchors
        except Exception as exc:
            logger.warning("[Timeline] Grounding failed: %s — returning empty anchors (no defaults)", exc)
    return {
        "income_anchors": None,
        "opportunity_base": 50,
        "psychographic_bases": {"stress": 55, "health": 65, "relationships": 60, "happiness": 52},
        "prompt_block": "WARNING: No live data available. Income estimates cannot be computed.",
        "salary_entry_lpa": None,
        "salary_mid_lpa": None,
        "salary_senior_lpa": None,
    }


# ── Deterministic causal transition ──────────────────────────────────────────

def _causal_transition(prev: dict, year_gap: int, personality_key: str) -> dict:
    """Pure-math score evolution — no LLM required."""
    bias = _PERSONALITY_BIAS.get(personality_key, 0)
    node_bias = _PERSONALITY_NODE_BIAS.get(personality_key, {})
    next_scores = {}
    for node in NODES:
        nb = node_bias.get(node, 0)
        drift = random.uniform(-4, 4) + bias * 0.3 + nb * 0.2
        next_scores[node] = prev.get(node, 50) + drift * year_gap
    for parent, child, weight in CAUSAL_EDGES:
        influence = (prev.get(parent, 50) - 50) * weight * year_gap * 0.4
        next_scores[child] = next_scores.get(child, 50) + influence
    return {node: _clamp(next_scores.get(node, 50)) for node in NODES}


def _deterministic_all_years(anchors: dict) -> dict:
    """
    Build all 3 timelines × 4 years using only _causal_transition.
    Used in offline mode or as fallback when the LLM call fails.

    Archetype starting conditions:
      A (Settler)  : low stress, high relationships, moderate income
      B (Climber)  : moderate stress, high career_growth, standard income
      C (Gambler)  : high stress, high opportunity, volatile income
    """
    cvars = anchors.get("_computed", {})
    stress_base = cvars.get("stress_score", 55)
    decision_type = anchors.get("_decision_type", "").lower()
    domain_id = get_domain(decision_type).value
    metrics = get_metrics_by_type(decision_type)
    has_salary = anchors.get("salary_entry_lpa") is not None

    if domain_id in ("education", "relationship", "health", "lifestyle") or not has_salary:
        income_base = 60
        _ARCHETYPE_YEAR1 = {
            "A": {
                "income":        _clamp(income_base - 5),
                "career_growth": _clamp(45),
                "stress":        _clamp(max(20, stress_base - 12)),
                "health":        _clamp(70),
                "relationships": _clamp(68),
                "happiness":     _clamp(60),
                "opportunity":   _clamp(anchors.get("opportunity_base", 82) - 8),
            },
            "B": {
                "income":        _clamp(income_base + 3),
                "career_growth": _clamp(55),
                "stress":        _clamp(stress_base + 3),
                "health":        _clamp(62),
                "relationships": _clamp(55),
                "happiness":     _clamp(56),
                "opportunity":   _clamp(anchors.get("opportunity_base", 82) + 5),
            },
            "C": {
                "income":        _clamp(income_base + 8),
                "career_growth": _clamp(60),
                "stress":        _clamp(stress_base + 15),
                "health":        _clamp(55),
                "relationships": _clamp(45),
                "happiness":     _clamp(48),
                "opportunity":   _clamp(anchors.get("opportunity_base", 82) + 16),
            },
        }
    else:
        income_base = 30
        _ARCHETYPE_YEAR1 = {
            "A": {
                "income":        _clamp(income_base - 3),
                "career_growth": _clamp(38),
                "stress":        _clamp(max(20, stress_base - 14)),
                "health":        _clamp(72),
                "relationships": _clamp(72),
                "happiness":     _clamp(62),
                "opportunity":   _clamp(anchors.get("opportunity_base", 82) - 10),
            },
            "B": {
                "income":        _clamp(income_base + 2),
                "career_growth": _clamp(52),
                "stress":        _clamp(stress_base + 2),
                "health":        _clamp(64),
                "relationships": _clamp(58),
                "happiness":     _clamp(54),
                "opportunity":   _clamp(anchors.get("opportunity_base", 82) + 3),
            },
            "C": {
                "income":        _clamp(income_base + 6),
                "career_growth": _clamp(58),
                "stress":        _clamp(stress_base + 16),
                "health":        _clamp(58),
                "relationships": _clamp(48),
                "happiness":     _clamp(50),
                "opportunity":   _clamp(anchors.get("opportunity_base", 82) + 14),
            },
        }

    result = {}
    for tl_key in TIMELINE_KEYS:
        pk = tl_key[-1]   # "A", "B", "C"
        year1 = _ARCHETYPE_YEAR1[pk]
        causal = {"Year1": year1}
        for prev_yr, next_yr in [("Year1", "Year3"), ("Year3", "Year5"), ("Year5", "Year10")]:
            causal[next_yr] = _causal_transition(causal[prev_yr], YEAR_GAPS[next_yr], pk)
        result[tl_key] = causal
    return result


# ── Batched LLM timeline generation ──────────────────────────────────────────

def _batch_generate_causal(decision: str, context: dict, anchors: dict) -> dict:
    """
    Single LLM call → all 3 timelines × 4 years.
    Returns {timeline_key: {year: {node: score}}}.
    Falls back to _deterministic_all_years on any failure.
    """
    cache = get_cache()
    qm    = get_quota_manager()

    # Build cache key from decision + context + grounding fingerprint
    grounding = anchors.get("_grounding", {})
    cache_key = cache.make_key(
        decision,
        json.dumps(context, sort_keys=True, default=str),
        str(grounding.get("salary_entry_lpa")),
        str(grounding.get("location")),
    )

    cached = cache.get(cache_key, model="batch_timeline")
    if cached is not None:
        logger.info("[Timeline] Cache hit — skipping LLM call")
        return cached

    if not qm.should_use_llm("timeline_batch"):
        logger.info("[Timeline] Quota mode '%s' — using deterministic fallback", qm.mode)
        return _deterministic_all_years(anchors)

    # Parse decision into structured options
    parsed_decision = parse_decision(decision)
    logger.info("[Timeline] Parsed decision: question=%s options=%s type=%s confidence=%d",
                parsed_decision.question[:60], parsed_decision.options,
                parsed_decision.decision_type, parsed_decision.confidence)
    decision_options_block = format_options_for_prompt(parsed_decision)

    template = _load_prompt("batch_timeline_prompt.txt")
    prompt = safe_template_substitute(
        template,
        decision=decision,
        decision_options=decision_options_block,
        context_json=json.dumps(context, indent=2, default=str),
        grounding_data=anchors["prompt_block"],
    )

    # Log the exact prompt being sent
    logger.info("[Timeline] === LLM PROMPT ===\n%s\n=== END PROMPT ===", prompt[:2000])

    try:
        raw = call_llm(prompt, temperature=0.65)
        qm.record_call()
        # Log the exact response received
        logger.info("[Timeline] === LLM RESPONSE ===\n%s\n=== END RESPONSE ===", raw[:1000])
        parsed = json.loads(raw)

        # Validate and normalise — clamp, fix degenerate zeros
        result = {}
        for tl_key in TIMELINE_KEYS:
            tl_data = parsed.get(tl_key, {})
            causal = {}
            for yr in YEARS:
                yr_raw = tl_data.get(yr, {})
                causal[yr] = _validate_year(yr_raw) if yr_raw else _causal_transition(
                    causal.get(YEARS[YEARS.index(yr) - 1], {}),
                    YEAR_GAPS[yr], tl_key[-1],
                )
            result[tl_key] = causal

        result = _validate_causal_scores(result)

        # Fill any entirely missing timelines with deterministic fallback
        det = _deterministic_all_years(anchors)
        for tl_key in TIMELINE_KEYS:
            if tl_key not in result:
                logger.warning("[Timeline] %s missing after validation — using deterministic", tl_key)
                result[tl_key] = det[tl_key]

        cache.set(cache_key, model="batch_timeline", response=result)
        logger.info("[Timeline] Batched LLM call succeeded — cached result")
        return result

    except Exception as exc:
        qm.record_error(is_rate_limit="rate" in str(exc).lower() or "429" in str(exc))
        logger.warning("[Timeline] Batched LLM failed: %s — deterministic fallback", exc)
        return _deterministic_all_years(anchors)


# ── Template-based narrative (no LLM) ────────────────────────────────────────

_NARRATIVE_TEMPLATES = {
    "low_stress_good_income": (
        "You are earning ~{lpa} LPA and managing your finances comfortably "
        "with ₹{disposable:,}/month disposable income. "
        "Stress is low at {stress}/100 — your work-life balance is holding."
    ),
    "high_stress_good_income": (
        "You are earning ~{lpa} LPA but the pace is taking a toll — "
        "stress sits at {stress}/100. "
        "Career growth is strong at {cg}/100, though health and relationships feel the pressure."
    ),
    "low_income_high_stress": (
        "Earning ~{lpa} LPA with stress at {stress}/100, the financial pressure is real. "
        "Disposable income is tight, limiting savings and flexibility."
    ),
    "mid_trajectory": (
        "You are progressing steadily — ~{lpa} LPA, stress {stress}/100, "
        "happiness {h}/100. Career growth at {cg}/100 suggests continued upward movement."
    ),
    "educational_strong": (
        "Your academic performance is strong — focus score {h}/100, "
        "stress manageable at {stress}/100. "
        "Preparation trajectory at {cg}/100 positions you well for competitive exams."
    ),
    "educational_mid": (
        "You are progressing through your academic preparation — "
        "focus at {h}/100, stress {stress}/100. "
        "Consistent effort at {cg}/100 is building toward your exam goals."
    ),
    "educational_stressed": (
        "Academic pressure is high at {stress}/100, but your preparation "
        "score of {cg}/100 shows steady progress. "
        "Focus on maintaining consistency over intensity."
    ),
}

def _pick_template(scores: dict, lpa: float | None, disposable: int, decision_type: str = "") -> str:
    stress = scores.get("stress", 50)
    h      = scores.get("happiness", 50)
    cg     = scores.get("career_growth", 50)
    ctx    = {"lpa": lpa if lpa is not None else 0, "stress": stress, "h": h, "cg": cg, "disposable": max(0, disposable)}

    if decision_type == "educational":
        if stress < 45:
            return _NARRATIVE_TEMPLATES["educational_strong"].format(**ctx)
        if stress >= 65:
            return _NARRATIVE_TEMPLATES["educational_stressed"].format(**ctx)
        return _NARRATIVE_TEMPLATES["educational_mid"].format(**ctx)

    if lpa is not None and stress < 45 and lpa >= 8:
        return _NARRATIVE_TEMPLATES["low_stress_good_income"].format(**ctx)
    if lpa is not None and stress >= 65 and lpa >= 8:
        return _NARRATIVE_TEMPLATES["high_stress_good_income"].format(**ctx)
    if lpa is not None and lpa < 6 and stress >= 55:
        return _NARRATIVE_TEMPLATES["low_income_high_stress"].format(**ctx)
    return _NARRATIVE_TEMPLATES["mid_trajectory"].format(**ctx)


def _build_narratives_llm(
    all_causal: dict,
    anchors: dict,
    decision: str,
    context: dict,
) -> dict:
    """
    Single LLM call → rich, unique narratives for all 3 timelines × 4 years.
    Falls back to template-based narratives on failure.
    """
    cache = get_cache()
    qm    = get_quota_manager()

    # Build a compact score summary for the prompt
    tl_scores = {}
    for tl_key in TIMELINE_KEYS:
        tl_scores[tl_key] = {}
        for yr in YEARS:
            scores = all_causal.get(tl_key, {}).get(yr, {})
            lpa    = _score_to_lpa_safe(scores.get("income", 50), anchors)
            tl_scores[tl_key][yr] = {**scores, "lpa": lpa}

    cache_key = cache.make_key(
        "narratives",
        decision,
        json.dumps(context, sort_keys=True, default=str),
        json.dumps({k: {yr: v.get("income") for yr, v in yrs.items()} for k, yrs in tl_scores.items()}),
    )

    cached = cache.get(cache_key, model="batch_narratives")
    if cached is not None:
        logger.info("[Timeline] Narrative cache hit")
        return cached

    if not qm.should_use_llm("timeline_batch"):
        return {}  # caller falls back to templates

    personalities = "\n".join(
        f"  {k}: {v}" for k, v in TIMELINE_PERSONALITIES.items()
    )
    cvars = anchors.get("_computed", {})

    # Parse decision for narrative context
    parsed_decision = parse_decision(decision)
    options_str = ", ".join(parsed_decision.options) if parsed_decision.options else "N/A"

    prompt = f"""You are a life simulation narrative writer.

DECISION: {decision}
DETECTED OPTIONS: {options_str}
PERSON: age {context.get('age', 'unknown')}, {context.get('location', 'India')}, {context.get('role', 'professional')}

TIMELINE ARCHETYPES:
{personalities}

CAUSAL SCORES (income score → LPA already computed):
{json.dumps(tl_scores, indent=2)}

CRITICAL INSTRUCTION:
The user's decision is: "{decision}"

Each timeline narrative MUST be ROOTED in this specific decision. Do NOT write
generic career narratives. Each timeline personality explores a different facet
of the same decision.

For example, if the decision is "CSE or AIML at VIT in 2026?":
- Timeline A should describe a stable software engineering career from CSE
- Timeline B should describe a strategic AI/ML career from AIML
- Timeline C should describe a high-risk/high-reward path, possibly switching

If the decision is "Should I quit my job to start a company?":
- Timeline A stays employed, builds side projects
- Timeline B takes a calculated leap with planning
- Timeline C quits immediately and goes all-in

Write a 2-3 sentence narrative paragraph for EACH timeline × EACH year.
- Use second person ("You are...")
- Be SPECIFIC: mention the actual LPA, stress level, and what that means for daily life
- Each timeline MUST sound DISTINCT:
    Timeline A (The Settler): grounded, content, community-focused language
    Timeline B (The Climber): driven, measured, achievement-oriented language
    Timeline C (The Gambler): urgent, high-stakes, feast-or-famine language
- Each year must show PROGRESSION from the previous year
- Do NOT use generic phrases like "things are going well" or "stress is low"
- Reference the decision options: {options_str}
- For Timeline C, Year10 must COMMIT to either triumph or cost — not both equally

Output ONLY valid JSON:
{{
  "Timeline A": {{"Year1": "...", "Year3": "...", "Year5": "...", "Year10": "..."}},
  "Timeline B": {{"Year1": "...", "Year3": "...", "Year5": "...", "Year10": "..."}},
  "Timeline C": {{"Year1": "...", "Year3": "...", "Year5": "...", "Year10": "..."}}
}}"""

    try:
        raw    = call_llm(prompt, temperature=0.8)
        qm.record_call()
        parsed = json.loads(raw)
        # Validate structure
        for tl in TIMELINE_KEYS:
            if tl not in parsed:
                raise ValueError(f"Missing timeline {tl} in narrative response")
            for yr in YEARS:
                if yr not in parsed[tl]:
                    raise ValueError(f"Missing {yr} in {tl}")
        cache.set(cache_key, model="batch_narratives", response=parsed)
        logger.info("[Timeline] LLM narratives generated ✓")
        return parsed
    except Exception as exc:
        qm.record_error(is_rate_limit="rate" in str(exc).lower() or "429" in str(exc))
        logger.warning("[Timeline] Narrative LLM failed: %s — template fallback", exc)
        return {}


def _build_narratives(causal_years: dict, anchors: dict, tl_key: str = "", llm_narratives: dict = None) -> dict:
    """Return narratives for one timeline — LLM result preferred, template fallback."""
    # Use LLM narratives if available for this timeline
    if llm_narratives and tl_key and tl_key in llm_narratives:
        return llm_narratives[tl_key]

    # Template fallback
    cvars         = anchors.get("_computed", {})
    disposable    = cvars.get("disposable_income", 0)
    decision_type = anchors.get("_decision_type", "").lower()
    narratives = {}
    for yr, scores in causal_years.items():
        lpa = _score_to_lpa_safe(scores.get("income", 50), anchors)
        narratives[yr] = _pick_template(scores, lpa, disposable, decision_type)
    return narratives


# ── Score interpretations ─────────────────────────────────────────────────────

def build_score_interpretations(causal_years: dict, anchors: dict) -> dict:
    grounding = anchors.get("_grounding", {})
    salary_source = grounding.get("data_source", "static_estimate")
    cpi_source = grounding.get("cpi_source", "static_estimate")
    decision_type = anchors.get("_decision_type", "").lower()
    is_educational = decision_type == "educational"
    interps = {}
    for yr, scores in causal_years.items():
        interps[yr] = {}
        for node, score in scores.items():
            if node == "income":
                if is_educational:
                    label = f"{score}/100 (academic/earning potential score)"
                    interps[yr][node] = {
                        "score": score, "label": label,
                        "source": "Educational projection (no salary data)",
                    }
                else:
                    lpa = _score_to_lpa_safe(score, anchors)
                    label = f"~{lpa} LPA" if lpa is not None else f"{score}/100 (salary data unavailable)"
                    interps[yr][node] = {
                        "score": score, "label": label,
                        "source": salary_source,
                    }
            elif node == "opportunity":
                rate = anchors.get("opportunity_base", 82)
                interps[yr][node] = {
                    "score": score,
                    "label": f"{score}/100 (base employment {rate}%)",
                    "source": cpi_source if grounding.get("live_unemployment") is not None else "static_estimate",
                }
            else:
                base = anchors.get("psychographic_bases", {}).get(node)
                label = f"{score}/100"
                if base is not None:
                    diff = score - base
                    direction = "above" if diff >= 0 else "below"
                    label = f"{score}/100 ({abs(diff)} pts {direction} baseline)"
                interps[yr][node] = {
                    "score": score, "label": label,
                    "source": "Psychographic baseline (India workforce surveys)",
                }
    return interps


# ── Decision analysis ─────────────────────────────────────────────────────────

def generate_analysis(decision: str, context: dict, anchors: dict) -> dict:
    cvars     = anchors.get("_computed", {})
    grounding = anchors.get("_grounding", {})
    if not cvars:
        return {}

    salary_lpa   = cvars.get("expected_salary_lpa", 0)
    monthly_inc  = cvars.get("monthly_income", 0)
    expenses     = cvars.get("monthly_expenses", 0)
    disposable   = cvars.get("disposable_income", 0)
    stress       = cvars.get("stress_score", 55)
    savings_rate = cvars.get("savings_rate_pct", 0)
    unemp        = grounding.get("live_unemployment") or 5.0
    cpi          = grounding.get("live_cpi") or 5.0
    gdp          = grounding.get("live_gdp_growth") or 6.5
    role         = grounding.get("role", "professional")
    location     = grounding.get("location", "India")
    cpi_year     = grounding.get("cpi_year", str(datetime.now().year))
    cpi_source   = grounding.get("cpi_source", "world_bank")

    qm = get_quota_manager()
    if qm.should_use_llm("synthesis"):
        template = _load_prompt("analysis_prompt.txt")
        prompt = (
            template
            .replace("{decision}",       decision)
            .replace("{career}",         role)
            .replace("{location}",       location)
            .replace("{salary}",         str(salary_lpa))
            .replace("{monthly_income}", f"{monthly_inc:,}")
            .replace("{expenses}",       f"{expenses:,}")
            .replace("{disposable}",     f"{disposable:,}")
            .replace("{stress}",         str(stress))
            .replace("{savings_rate}",   str(savings_rate))
            .replace("{unemployment}",   f"{unemp:.1f}")
            .replace("{cpi}",            f"{cpi:.1f}")
            .replace("{gdp_growth}",     f"{gdp:.1f}")
            .replace("{year}",           cpi_year)
            .replace("{source}",         cpi_source)
        )
        try:
            raw = call_llm(prompt, temperature=0.4)
            qm.record_call()
            result = json.loads(raw)
            for key in ("summary", "five_year_outlook", "tradeoffs", "scenario_shifts"):
                if key not in result:
                    raise ValueError(f"Missing key: {key}")
            return result
        except Exception as exc:
            qm.record_error(is_rate_limit="rate" in str(exc).lower())
            logger.warning("[Analysis] LLM failed: %s — deterministic fallback", exc)

    # Deterministic fallback
    disp_sign = "+" if disposable >= 0 else ""
    return {
        "summary": {
            "career_path":         f"{role.title()} in {location}.",
            "financial_situation": (
                f"Earning ₹{salary_lpa} LPA (₹{monthly_inc:,}/month). "
                f"Expenses ₹{expenses:,}/month, disposable {disp_sign}₹{disposable:,}/month."
            ),
            "stress_level":        f"Computed stress {stress}/100 (financial + unemployment + inflation components).",
            "savings_potential":   f"Savings rate {savings_rate}% of monthly income.",
        },
        "five_year_outlook": (
            f"With ₹{disposable:,}/month disposable, savings are "
            f"{'feasible' if disposable > 0 else 'constrained'}. "
            f"Unemployment {unemp:.1f}%, GDP {gdp:.1f}% — "
            f"{'stable' if unemp < 6 else 'uncertain'} job market. "
            f"CPI {cpi:.1f}% erodes purchasing power over time."
        ),
        "tradeoffs": {
            "gained":     f"Stable ₹{salary_lpa} LPA in {grounding.get('industry','professional')} sector with {unemp:.1f}% unemployment.",
            "sacrificed": f"Stress {stress}/100 reflects ongoing financial and economic pressure.",
        },
        "scenario_shifts": {
            "higher_salary":      "Higher salary increases disposable income and reduces financial stress.",
            "lower_salary":       "Lower salary may push disposable income negative given current expense levels.",
            "economic_downturn":  "Rising unemployment or GDP contraction would reduce opportunity and increase stress.",
        },
    }


# ── Public API ────────────────────────────────────────────────────────────────

def generate_timelines(
    decision: str,
    context: dict,
    chaos_events: dict | None = None,
) -> dict:
    """
    Generate 3 timelines. Budget: 1 LLM call (batched), 0 in low/offline mode.

    Returns dict where each timeline has:
      Year1..Year10       : narrative strings
      _causal             : {year: {node: score}}
      _interpretations    : {year: {node: {score, label, source}}}
      _grounding          : raw grounding metadata
      _computed           : computed financial variables
    Plus top-level:
      _analysis           : structured decision analysis
    """
    # ── Validation: ensure decision context exists ───────────────────────────
    from input_validator import is_likely_meaningful
    valid, msg = is_likely_meaningful(decision)
    if not valid:
        raise ValueError(f"Invalid decision: {msg}")

    # ── Parse and validate decision options ──────────────────────────────────
    parsed = parse_decision(decision)
    logger.info("[Timeline] ===== NEW SIMULATION =====")
    logger.info("[Timeline] Decision: %s", decision)
    logger.info("[Timeline] Parsed options: %s", parsed.options)
    logger.info("[Timeline] Decision type: %s", parsed.decision_type)
    logger.info("[Timeline] Parsing confidence: %d%%", parsed.confidence)

    # Low-confidence handling: if we can't parse the decision, don't silently
    # generate unrelated outcomes
    if parsed.confidence < 50:
        logger.warning("[Timeline] Low parsing confidence (%d%%) for decision: %s",
                       parsed.confidence, decision)
        # Still proceed but flag it — the frontend can decide to show a warning
        context["_low_confidence"] = True
        context["_parsed_decision"] = {
            "confidence": parsed.confidence,
            "options": parsed.options,
        }

    anchors      = _get_anchors(decision, context)
    chaos_events = chaos_events or {}

    # 1 LLM call (or 0 in low/offline mode) — all timelines × all years
    all_causal = _batch_generate_causal(decision, context, anchors)

    # 1 LLM call — rich narratives for all timelines × all years
    llm_narratives = _build_narratives_llm(all_causal, anchors, decision, context)

    enriched = {}
    for tl_key in TIMELINE_KEYS:
        tl_chaos = chaos_events.get(tl_key, [])
        causal   = {}

        for yr in YEARS:
            raw_scores = all_causal.get(tl_key, {}).get(yr, {})
            scores     = raw_scores if raw_scores else _causal_transition(
                causal.get(YEARS[YEARS.index(yr) - 1], {}),
                YEAR_GAPS[yr], tl_key[-1],
            )
            causal[yr] = _apply_chaos_deltas(scores, tl_chaos, yr)

        # Post-chaos validation — fix income=0 re-introduced by events
        for yr in YEARS:
            if causal.get(yr, {}).get("income", 50) < 5:
                logger.warning("[Timeline] Post-chaos degenerate income=%s in %s/%s — clamping to 5",
                               causal[yr]["income"], tl_key, yr)
                causal[yr]["income"] = 5

        narratives      = _build_narratives(causal, anchors, tl_key=tl_key, llm_narratives=llm_narratives)
        interpretations = build_score_interpretations(causal, anchors)

        enriched[tl_key] = {
            **narratives,
            "_causal":          causal,
            "_interpretations": interpretations,
            "_grounding":       anchors.get("_grounding", {}),
            "_computed":        anchors.get("_computed", {}),
        }

    enriched["_analysis"] = generate_analysis(decision, context, anchors)
    return enriched


# ── Pivot timeline generation ─────────────────────────────────────────────────

def generate_pivot_timeline(
    original_timeline: dict,
    event_year: int,
    alternative_outcome: str,
    decision: str,
    context: dict,
) -> dict:
    """
    Branch a timeline from event_year onward with an alternative outcome.

    - Years BEFORE event_year are kept exactly from original_timeline.
    - Years FROM event_year onward are re-simulated with the alternative
      outcome injected as a forced context override.
    - Uses a dedicated LLM call (not cached with the main simulation key)
      so the pivot always produces a genuinely different result.

    Returns a single timeline dict with:
      Year1..Year10  : narrative strings
      _causal        : {year: {node: score}}
      _interpretations, _grounding, _computed
    """
    anchors = _get_anchors(decision, context)
    qm = get_quota_manager()

    # Map event_year int → YEARS key
    year_key = f"Year{event_year}"
    pivot_idx = YEARS.index(year_key) if year_key in YEARS else 0

    # ── Preserve original causal scores for years before the pivot ────────────
    orig_causal = original_timeline.get("_causal", {})
    preserved_causal = {}
    for yr in YEARS[:pivot_idx]:
        preserved_causal[yr] = orig_causal.get(yr, {})

    # ── Seed scores at the pivot year from the original, then apply boost ─────
    # The alternative outcome is parsed for positive/negative signal
    positive_keywords = [
        "promoted", "promotion", "raise", "hired", "funded", "succeeded",
        "won", "launched", "grew", "improved", "recovered", "better",
    ]
    negative_keywords = [
        "fired", "failed", "quit", "lost", "rejected", "declined",
        "worse", "struggled", "bankrupt", "sick",
    ]
    alt_lower = alternative_outcome.lower()
    is_positive = any(kw in alt_lower for kw in positive_keywords)
    is_negative = any(kw in alt_lower for kw in negative_keywords)

    # Boost/penalty applied at pivot year
    boost = {}
    if is_positive:
        boost = {"income": +12, "career_growth": +15, "happiness": +10,
                 "stress": -8, "opportunity": +10}
    elif is_negative:
        boost = {"income": -10, "career_growth": -12, "happiness": -8,
                 "stress": +12, "opportunity": -8}
    else:
        # Neutral alternative — moderate positive shift (user is exploring)
        boost = {"income": +6, "career_growth": +8, "happiness": +5,
                 "stress": -4, "opportunity": +5}

    # Seed from original Year at pivot point (or Year1 if pivot is Year1)
    seed_yr = YEARS[max(0, pivot_idx - 1)] if pivot_idx > 0 else YEARS[0]
    seed_scores = dict(orig_causal.get(seed_yr, {}))
    if not seed_scores:
        seed_scores = {node: 50 for node in NODES}

    pivot_scores = {
        node: _clamp(seed_scores.get(node, 50) + boost.get(node, 0))
        for node in NODES
    }
    preserved_causal[year_key] = pivot_scores

    # ── Propagate forward from pivot year using causal transitions ────────────
    pivot_causal = dict(preserved_causal)
    remaining_years = YEARS[pivot_idx + 1:]
    for i, yr in enumerate(remaining_years):
        prev_yr = YEARS[pivot_idx + i]
        pivot_causal[yr] = _causal_transition(
            pivot_causal[prev_yr], YEAR_GAPS[yr], "B"  # balanced personality for pivot
        )

    # ── Try LLM narrative for the pivot branch ────────────────────────────────
    pivot_narratives = {}
    if qm.should_use_llm("timeline_batch"):
        tl_scores_for_prompt = {}
        for yr in YEARS:
            scores = pivot_causal.get(yr, {})
            lpa = _score_to_lpa_safe(scores.get("income", 50), anchors)
            tl_scores_for_prompt[yr] = {**scores, "lpa": lpa}

        prompt = f"""You are a life simulation narrative writer.

ORIGINAL DECISION: {decision}
PIVOT EVENT: At Year {event_year}, instead of what was originally happening,
the person experienced: "{alternative_outcome}"

This is a BRANCHED timeline — years before Year {event_year} are unchanged,
but from Year {event_year} onward, this alternative outcome reshapes everything.

CAUSAL SCORES for the pivot branch (income score → LPA already computed):
{json.dumps(tl_scores_for_prompt, indent=2)}

Write a 2-3 sentence narrative for EACH year showing how the pivot changed things.
- For years BEFORE Year {event_year}: briefly acknowledge the original path
- For Year {event_year} and AFTER: show how "{alternative_outcome}" changed the trajectory
- Use second person ("You are...")
- Be SPECIFIC: mention the actual LPA, stress level, and what the pivot meant
- Show clear cause-and-effect from the pivot event

Output ONLY valid JSON:
{{
  "Year1": "...",
  "Year3": "...",
  "Year5": "...",
  "Year10": "..."
}}"""

        try:
            raw = call_llm(prompt, temperature=0.8)
            qm.record_call()
            parsed = json.loads(raw)
            for yr in YEARS:
                if yr in parsed:
                    pivot_narratives[yr] = parsed[yr]
            logger.info("[Pivot] LLM narratives generated ✓")
        except Exception as exc:
            qm.record_error(is_rate_limit="rate" in str(exc).lower() or "429" in str(exc))
            logger.warning("[Pivot] LLM narrative failed: %s — template fallback", exc)

    # ── Template fallback for any missing years ───────────────────────────────
    cvars = anchors.get("_computed", {})
    disposable = cvars.get("disposable_income", 0)
    for yr in YEARS:
        if yr not in pivot_narratives:
            scores = pivot_causal.get(yr, {})
            lpa = _score_to_lpa_safe(scores.get("income", 50), anchors)
            if yr == year_key or YEARS.index(yr) >= pivot_idx:
                base = _pick_template(scores, lpa, disposable)
                pivot_narratives[yr] = (
                    f"[Pivot: {alternative_outcome[:60]}] {base}"
                )
            else:
                pivot_narratives[yr] = original_timeline.get(yr, _pick_template(scores, lpa, disposable))

    interpretations = build_score_interpretations(pivot_causal, anchors)

    return {
        **pivot_narratives,
        "_causal": pivot_causal,
        "_interpretations": interpretations,
        "_grounding": anchors.get("_grounding", {}),
        "_computed": anchors.get("_computed", {}),
    }
