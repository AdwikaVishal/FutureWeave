"""
Decision Analysis Agent

Analyses a user's decision description and returns a structured profile:
  decision_type, core_goal, biggest_fear, time_horizon,
  risk_tolerance, emotion_score, keywords
"""
import json
import logging
import os

from llm_client import call_llm
from llm_cache import get_cache
from quota_manager import get_quota_manager
from input_validator import safe_template_substitute

logger = logging.getLogger(__name__)

_DECISION_TYPES = [
    "Career Pivot",
    "Startup vs Job",
    "Relocation",
    "Higher Education",
    "Relationship",
    "Financial",
    "Other",
]


def _load_prompt() -> str:
    path = os.path.join(os.path.dirname(__file__), "..", "prompts", "decision_analysis_prompt.txt")
    with open(path) as f:
        return f.read()


def _keyword_fallback(decision: str, demographics: dict) -> dict:
    """Deterministic fallback when LLM is unavailable."""
    text = decision.lower()
    if any(w in text for w in ["startup", "business", "found", "venture"]):
        dtype = "Startup vs Job"
    elif any(w in text for w in ["move", "relocat", "city", "country"]):
        dtype = "Relocation"
    elif any(w in text for w in ["mba", "degree", "college", "study", "university"]):
        dtype = "Higher Education"
    elif any(w in text for w in ["job", "career", "switch", "pivot", "role"]):
        dtype = "Career Pivot"
    elif any(w in text for w in ["invest", "money", "loan", "debt", "financial"]):
        dtype = "Financial"
    elif any(w in text for w in ["marry", "relationship", "partner", "divorce"]):
        dtype = "Relationship"
    else:
        dtype = "Other"

    return {
        "decision_type":  dtype,
        "core_goal":      "Improve quality of life and career prospects.",
        "biggest_fear":   "Making the wrong choice and losing stability.",
        "time_horizon":   "Mid-term (2–5 years)",
        "risk_tolerance": demographics.get("risk_tolerance", "Medium").capitalize(),
        "emotion_score":  "50",
        "keywords":       [w for w in text.split() if len(w) > 4][:8],
    }


def _validate(result: dict) -> dict:
    if result.get("decision_type") not in _DECISION_TYPES:
        result["decision_type"] = "Other"
    try:
        score = int(str(result.get("emotion_score", 50)))
        result["emotion_score"] = str(max(0, min(100, score)))
    except (ValueError, TypeError):
        result["emotion_score"] = "50"
    if not isinstance(result.get("keywords"), list):
        result["keywords"] = []
    return result


def analyze_decision(
    decision: str,
    demographics: dict,
    location: str,
    career_stage: str,
) -> dict:
    """
    Returns:
        {
          "decision_type": str,
          "core_goal":     str,
          "biggest_fear":  str,
          "time_horizon":  str,
          "risk_tolerance": str,
          "emotion_score": str,   # "0"–"100"
          "keywords":      list[str],
        }
    """
    cache = get_cache()
    qm    = get_quota_manager()

    cache_key = cache.make_key("decision_analysis", decision, location, career_stage,
                               json.dumps(demographics, sort_keys=True, default=str))
    cached = cache.get(cache_key, model="decision_analysis")
    if cached is not None:
        logger.info("[DecisionAnalysis] Cache hit")
        return cached

    if not qm.should_use_llm("synthesis"):
        logger.info("[DecisionAnalysis] Offline mode — keyword fallback")
        return _keyword_fallback(decision, demographics)

    template = _load_prompt()
    prompt = safe_template_substitute(
        template,
        decision=decision,
        demographics=json.dumps(demographics, default=str),
        location=location,
        career_stage=career_stage,
    )

    try:
        raw    = call_llm(prompt, temperature=0.4)
        qm.record_call()
        result = json.loads(raw)
        result = _validate(result)
        cache.set(cache_key, model="decision_analysis", response=result)
        logger.info("[DecisionAnalysis] LLM analysis complete")
        return result

    except Exception as exc:
        qm.record_error(is_rate_limit="429" in str(exc) or "rate" in str(exc).lower())
        logger.warning("[DecisionAnalysis] LLM failed: %s — keyword fallback", exc)
        return _keyword_fallback(decision, demographics)
