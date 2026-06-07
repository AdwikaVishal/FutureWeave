"""
Simulation Engine — fully deterministic pipeline.

LLM budget per simulation:
  - 0 calls in deterministic mode (default)
  - 1 optional call for final narrative formatting (llm_format=True)

This replaces the old 4-5 LLM-call pipeline while producing equivalent
or better structured output.  The engine never CALLS an LLM internally —
if llm_format is requested it delegates to the caller's formatter.
"""

import json
import logging
import os
import traceback
from datetime import datetime

from decision_parser import parse_decision
from career_profiles import get_profile, get_profile_or_default, validate_profile
from domains import (
    get_metrics_by_type, get_archetype_label, get_regrets, get_letter,
    get_domain, DOMAIN_METRICS, DecisionDomain,
)

logger = logging.getLogger(__name__)


def _fmt_pct(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}%"


def _fmt_safe(value, fmt: str) -> str:
    if value is None:
        return "N/A"
    return f"{value:{fmt}}"


try:
    from agents.timeline import (
        _deterministic_all_years,
        _causal_transition,
        _score_to_lpa_safe,
        _validate_causal_scores,
        _apply_chaos_deltas,
        _build_narratives,
        _pick_template,
        build_score_interpretations,
        TIMELINE_KEYS, YEARS, YEAR_GAPS,
        NODES, CAUSAL_EDGES,
    )
    _TIMELINE_AVAILABLE = True
except ImportError as exc:
    _TIMELINE_AVAILABLE = False
    logger.warning("[SimEngine] timeline agent import failed: %s", exc)

try:
    from agents.synthesis import (
        _fallback_regret,
        _fallback_letter,
        _fallback_comparison,
        TIMELINE_PERSONALITIES,
    )
    _SYNTHESIS_AVAILABLE = True
except ImportError as exc:
    _SYNTHESIS_AVAILABLE = False
    logger.warning("[SimEngine] synthesis agent import failed: %s", exc)

try:
    from data_grounding import (
        get_grounding_data, build_score_anchors,
        compute_core_variables, score_to_lpa,
    )
    _GROUNDING_AVAILABLE = True
except ImportError as exc:
    _GROUNDING_AVAILABLE = False
    logger.warning("[SimEngine] data_grounding import failed: %s", exc)

try:
    from agents.chaos import apply_chaos
    _CHAOS_AVAILABLE = True
except ImportError:
    _CHAOS_AVAILABLE = False


def validate_simulation_input(anchors: dict) -> dict:
    """Validate all input dicts before simulation begins.
    
    Checks:
    - No strings where dicts expected
    - No None values
    - All required fields present
    - Correct types
    
    Returns the validated anchors dict. Raises TypeError on validation failure.
    """
    if not isinstance(anchors, dict):
        raise TypeError(f"Expected dict for anchors, got {type(anchors).__name__}")
    
    computed = anchors.get("_computed", {})
    if computed is not None and not isinstance(computed, dict):
        raise TypeError(
            f"Expected dict for anchors['_computed'], "
            f"got {type(computed).__name__}: {computed!r}"
        )
    
    grounding = anchors.get("_grounding", {})
    if grounding is not None and not isinstance(grounding, dict):
        raise TypeError(
            f"Expected dict for anchors['_grounding'], "
            f"got {type(grounding).__name__}: {grounding!r}"
        )
    
    for key in ("income_anchors", "opportunity_base", "psychographic_bases", "prompt_block"):
        val = anchors.get(key)
        if val is not None:
            if key == "prompt_block":
                if not isinstance(val, str):
                    raise TypeError(
                        f"Expected str for anchors['{key}'], "
                        f"got {type(val).__name__}"
                    )
            elif not isinstance(val, (dict, int, float)):
                raise TypeError(
                    f"Expected numeric/dict for anchors['{key}'], "
                    f"got {type(val).__name__}: {val!r}"
                )
    
    return anchors


def _validate_profile_before_use(profile: dict, context: str) -> dict:
    """Defensive check — never allow .get() on a string."""
    if not isinstance(profile, dict):
        raise TypeError(
            f"Expected dict for {context}, got {type(profile).__name__}: {profile!r}"
        )
    return profile


def _get_archetype_labels(decision_type: str = "") -> dict:
    domain_id = get_domain(decision_type).value
    return {
        "Timeline A": get_archetype_label(domain_id, "A").split(":")[0] if ":" in get_archetype_label(domain_id, "A") else "Path A",
        "Timeline B": get_archetype_label(domain_id, "B").split(":")[0] if ":" in get_archetype_label(domain_id, "B") else "Path B",
        "Timeline C": get_archetype_label(domain_id, "C").split(":")[0] if ":" in get_archetype_label(domain_id, "C") else "Path C",
    }


def _get_archetype_descriptions(decision_type: str = "") -> dict:
    domain_id = get_domain(decision_type).value
    return {
        "Timeline A": get_archetype_label(domain_id, "A"),
        "Timeline B": get_archetype_label(domain_id, "B"),
        "Timeline C": get_archetype_label(domain_id, "C"),
    }


def _build_synthesis_fallback(
    timelines: dict,
    decision: str,
    anchors: dict | None = None,
) -> dict:
    """Deterministic synthesis: regrets + letters + comparison. 0 LLM calls.
    Uses domain-specific templates when available."""
    anchors = anchors or {}
    decision_type = anchors.get("_decision_type", "").lower()
    domain_id = get_domain(decision_type).value
    regrets = {}
    letters = {}
    tl_keys = [k for k in timelines if not k.startswith("_")]

    for tl_key in tl_keys:
        tl = timelines.get(tl_key, {})
        arch_key = tl_key[-1]  # "A", "B", "C"
        regret = _fallback_regret(tl_key, tl, domain_id, arch_key)
        regrets[tl_key] = regret
        letters[tl_key] = _fallback_letter(tl_key, tl, regret, domain_id, arch_key)

    comparison = _fallback_comparison(timelines)
    return {"regrets": regrets, "letters": letters, "comparison": comparison}


def run_simulation(
    decision: str,
    context: dict,
    chaos_events: dict | None = None,
    llm_format: bool = False,
    llm_formatter=None,
) -> dict:
    """
    Run a complete simulation with ZERO mandatory LLM calls.

    Parameters
    ----------
    decision : str
        User's decision text (e.g. "CSE or AIML at VIT?").
    context : dict
        User demographics and preferences.
    chaos_events : dict | None
        Optional pre-generated chaos events per timeline.
    llm_format : bool
        If True, calls llm_formatter once for final narrative polish.
    llm_formatter : callable or None
        Function(synthesis_result, timelines, decision, context) -> formatted dict.
        Only called when llm_format=True.

    Returns
    -------
    dict
        Complete simulation response (same shape as /simulate).
    """
    from input_validator import is_likely_meaningful

    valid, msg = is_likely_meaningful(decision)
    if not valid:
        raise ValueError(f"Invalid decision: {msg}")

    parsed = parse_decision(decision)
    logger.info(
        "[SimEngine] Parsed: options=%s type=%s confidence=%d",
        parsed.options, parsed.decision_type, parsed.confidence,
    )

    # ── Grounding (0 LLM) ──────────────────────────────────────────────
    anchors = _get_anchors(decision, context, parsed)
    chaos_events = chaos_events or {}

    # ── Timeline scores (0 LLM) ────────────────────────────────────────
    all_causal = _deterministic_all_years(anchors)
    all_causal = _validate_causal_scores(all_causal)

    # ── Apply chaos ────────────────────────────────────────────────────
    for tl_key in TIMELINE_KEYS:
        tl_chaos = chaos_events.get(tl_key, [])
        for yr in YEARS:
            scores = all_causal.get(tl_key, {}).get(yr, {})
            scores.update(_apply_chaos_deltas(scores, tl_chaos, yr))

    # ── Post-chaos validation (fix income=0 re-introduced by chaos) ────
    for tl_key in TIMELINE_KEYS:
        for yr in YEARS:
            nodes = all_causal.get(tl_key, {}).get(yr, {})
            if nodes.get("income", 50) < 5:
                logger.warning("[SimEngine] Post-chaos degenerate income=%s in %s/%s — clamping to 5", nodes["income"], tl_key, yr)
                nodes["income"] = 5

    # ── Build timelines with narratives (0 LLM) ────────────────────────
    enriched = _build_enriched_timelines(all_causal, anchors)

    # ── Synthesis (0 LLM) ──────────────────────────────────────────────
    synthesis = _build_synthesis_fallback(enriched, decision, anchors)

    # ── Decision analysis (0 LLM) ──────────────────────────────────────
    analysis = _build_analysis(enriched, anchors, context)

    # ── Optional: single LLM formatting call ──────────────────────────
    if llm_format and llm_formatter is not None:
        try:
            formatted = llm_formatter(synthesis, enriched, decision, context)
            if formatted:
                synthesis = formatted
        except Exception as exc:
            logger.warning("[SimEngine] LLM formatter failed: %s — keeping deterministic", exc)

    # ── Debug log + assertions before simulation ───────────────────────
    decision_type = anchors.get("_decision_type", "unknown")
    domain_id = anchors.get("_domain_id", get_domain(decision_type).value)
    grounding = anchors.get("_grounding", {})
    cvars = anchors.get("_computed", {})
    logger.info(
        "TYPE=%s DOMAIN=%s ROLE=%s SALARY=%s JOB_MARKET=%s",
        decision_type, domain_id,
        grounding.get("role"),
        grounding.get("salary_entry_lpa") is not None,
        grounding.get("job_market") is not None,
    )
    income_irrelevant = {"education", "relationship", "health", "lifestyle"}
    if domain_id in income_irrelevant:
        assert grounding.get("role") is None or grounding.get("role") == "default", \
            f"Career path leak: {domain_id} decision has role={grounding.get('role')!r}"
        assert grounding.get("salary_entry_lpa") is None, \
            f"Career path leak: {domain_id} decision has salary data"
        assert grounding.get("job_market") is None, \
            f"Career path leak: {domain_id} decision has job market data"

    # ── Build agent outputs, events, synthesis wrapper ─────────────────
    agent_outputs = _build_agent_outputs(all_causal, anchors, context, analysis)
    events = _build_events(agent_outputs, all_causal, anchors)

    comparison_data = synthesis.get("comparison", {})

    synthesis_wrapper = {
        "comparison": comparison_data,
        "regrets": synthesis.get("regrets", {}),
        "letters": synthesis.get("letters", {}),
        "recommendation": _build_recommendation(analysis, comparison_data, anchors),
        "confidence": _build_confidence_summary(agent_outputs, data_confidence=85, decision_type=decision_type),
    }

    # ── Build timeline labels (use real options when available) ────────
    timeline_labels = {}
    timeline_descriptions = {}
    options = parsed.options

    if len(options) >= 3:
        timeline_labels = {
            "Timeline A": options[0],
            "Timeline B": options[1],
            "Timeline C": options[2],
        }
        timeline_descriptions = {
            "Timeline A": f"Following the {options[0]} path.",
            "Timeline B": f"Following the {options[1]} path.",
            "Timeline C": f"Following the {options[2]} path.",
        }
    elif len(options) == 2:
        timeline_labels = {
            "Timeline A": options[0],
            "Timeline B": options[1],
            "Timeline C": f"{options[0]} + {options[1]} Hybrid",
        }
        timeline_descriptions = {
            "Timeline A": f"Focusing primarily on {options[0]}.",
            "Timeline B": f"Focusing primarily on {options[1]}.",
            "Timeline C": f"Blending {options[0]} and {options[1]}.",
        }
    else:
        timeline_labels = _get_archetype_labels(decision_type)
        timeline_descriptions = _get_archetype_descriptions(decision_type)

    # ── Assemble response ──────────────────────────────────────────────
    causal_data = {}
    interpretations = {}
    grounding_meta = {}
    computed_meta = {}
    timelines_out = {}

    for tl_key in TIMELINE_KEYS:
        tl = enriched.get(tl_key, {})
        timelines_out[tl_key] = {yr: tl.get(yr, "") for yr in YEARS}
        causal_data[tl_key] = tl.get("_causal", {})
        interpretations[tl_key] = tl.get("_interpretations", {})
        grounding_meta[tl_key] = tl.get("_grounding", {})
        computed_meta[tl_key] = tl.get("_computed", {})

    return {
        "decision": decision,
        "context": context,
        "archetype_labels": timeline_labels,
        "archetype_descriptions": timeline_descriptions,
        "timeline_labels": timeline_labels,
        "domain": domain_id,
        "timelines": timelines_out,
        "causal_data": causal_data,
        "interpretations": interpretations,
        "grounding": grounding_meta,
        "computed": computed_meta,
        "analysis": analysis,
        "synthesis": synthesis_wrapper,
        "agent_outputs": agent_outputs,
        "events": events,
        "regrets": synthesis.get("regrets", {}),
        "letters": synthesis.get("letters", {}),
        "comparison": synthesis.get("comparison", {}),
        "decision_parsing": {
            "options": parsed.options,
            "type": parsed.decision_type,
            "confidence": parsed.confidence,
            "institution": parsed.institution,
            "year": parsed.year,
        },
        "data_confidence": 85,
        "data_confidence_explanation": (
            "Deterministic simulation based on domain-specific models."
        ),
        "data_warnings": [],
        "data_monitoring": {},
    }


def _build_agent_outputs(
    all_causal: dict,
    anchors: dict,
    context: dict,
    analysis: dict,
) -> dict:
    """Generate deterministic agent outputs from causal data. 0 LLM calls.
    Domain-aware: uses domain-specific metrics and reasoning."""
    cvars = anchors.get("_computed", {})
    decision_type = anchors.get("_decision_type", "").lower()
    domain_id = get_domain(decision_type).value
    metrics = get_metrics_by_type(decision_type)
    location = context.get("location", "India")
    industry = context.get("industry", "technology")

    # Build dynamic agent outputs based on domain metrics
    outputs = {}
    primary = metrics.primary_metric
    nodes = metrics.nodes

    for node in nodes:
        scores = {y: all_causal.get("Timeline B", {}).get(y, {}).get(node, 50) for y in YEARS}
        avg = sum(scores.values()) / max(len(scores), 1)

        label = node.replace("_", " ").title()
        weight = metrics.weights.get(node, 0)

        evidence = _build_domain_evidence(node, domain_id, industry, location)
        assumptions = _build_domain_assumptions(node, domain_id)
        reasoning = _build_domain_reasoning(node, avg, domain_id, primary)

        outputs[node] = {
            "output": {
                "score": round(avg, 1),
                "confidence": round(0.60 + abs(avg - 50) / 100.0 * 0.3, 2),
                "reasoning": reasoning,
                "evidence": evidence,
                "assumptions": assumptions,
                "impact": round(avg - 50, 1),
                "year_scores": scores,
                "weight": weight,
            },
            "confidence": round(0.60 + abs(avg - 50) / 100.0 * 0.3, 2),
            "latency_ms": 0,
            "error": None,
        }

    return outputs


def _build_domain_evidence(node: str, domain_id: str, industry: str, location: str) -> list[str]:
    evidence_map = {
        "education": {
            "learning_growth": ["Curriculum depth and teaching quality drive skill acquisition", "Peer learning accelerates understanding"],
            "placement_potential": ["Placement records show 70-90% placement rates for top branches", "Company visits depend on college reputation"],
            "research_opportunities": ["Research output correlates with faculty quality", "Publication opportunities vary by department"],
            "future_optionality": ["Broad fields keep more career doors open", "Specialization depth creates niche advantages"],
            "academic_pressure": ["Exam schedules create cyclical stress patterns", "Competitive peer environment increases pressure"],
            "skill_development": ["Industry-relevant skills improve employability", "Projects and internships bridge academia and industry"],
        },
        "business": {
            "revenue_potential": ["Market size and TAM determine ceiling", "Revenue model sustainability critical for growth"],
            "failure_risk": ["90% of startups fail within first 5 years", "Team quality is the strongest predictor of success"],
            "market_opportunity": ["Timing is critical — being too early is same as being wrong", "Market growth rate determines runway"],
            "burn_rate": ["Cash management is the #1 cause of startup death", "Runway determines how many pivots you can afford"],
            "wealth_creation": ["Equity compounding creates asymmetric upside", "Exit multiples vary dramatically by sector"],
        },
        "relocation": {
            "cost_of_living": [f"Housing costs in {location} vary significantly by neighborhood", "Local taxes and utilities impact monthly budget"],
            "career_access": [f"Job market density in {location} determines opportunity frequency", "Industry clusters create network effects"],
            "social_support": ["Existing networks reduce relocation friction", "Community building takes 6-18 months"],
            "quality_of_life": "Walkability, air quality, and green spaces impact daily satisfaction",
            "safety": "Crime rates and neighborhood safety affect long-term happiness",
        },
        "financial": {
            "wealth_growth": ["Compound interest accelerates after Year 7", "Asset allocation determines 90% of returns"],
            "cash_flow": ["Positive cash flow is the foundation of financial health", "Emergency funds reduce forced selling risk"],
            "risk": "Diversification is the only free lunch in finance",
            "liquidity": "Cash reserves provide optionality in market downturns",
        },
        "relationship": {
            "emotional_health": "Emotional attunement predicts relationship satisfaction",
            "compatibility": "Shared values matter more than shared interests long-term",
            "communication": "Communication quality is the strongest predictor of relationship success",
        },
        "health": {
            "treatment_efficacy": "Early intervention significantly improves outcomes",
            "recovery_rate": "Recovery timelines vary based on treatment adherence",
            "quality_of_life": "Quality of life considerations matter as much as clinical outcomes",
        },
    }
    domain_evidence = evidence_map.get(domain_id, {})
    specific = domain_evidence.get(node, [])
    if isinstance(specific, str):
        return [specific]
    return specific if specific else [f"{node.replace('_', ' ').title()} trajectory over the projection period."]


def _build_domain_assumptions(node: str, domain_id: str) -> list[str]:
    shared = ["External conditions remain broadly stable", "No major personal crises interrupt trajectory"]
    domain_specific = {
        "education": ["Academic performance maintained at current level", "Placement market remains healthy", "No major curriculum changes"],
        "business": ["Market conditions remain favourable", "Funding environment stays accessible", "Team remains intact through growth"],
        "relocation": ["Immigration policies remain stable", "Cost of living trends continue predictably", "Personal circumstances support the move"],
        "financial": ["Market returns follow historical averages", "Tax regime remains broadly unchanged", "No hyperinflation or currency crisis"],
        "relationship": ["Both partners invest equally in growth", "External stressors remain manageable"],
        "health": ["Treatment protocols remain accessible", "Support system stays engaged"],
    }
    return domain_specific.get(domain_id, shared) + shared[:1]


def _build_domain_reasoning(node: str, avg: float, domain_id: str, primary_metric: str) -> str:
    templates = {
        "education": {
            "learning_growth": f"Learning trajectory at {avg:.0f}/100 — academic skill acquisition progressing as expected.",
            "placement_potential": f"Placement outlook at {avg:.0f}/100 — {'strong' if avg > 60 else 'moderate'} industry demand for graduates.",
            "academic_pressure": f"Academic pressure at {avg:.0f}/100 — {'elevated' if avg > 60 else 'manageable'} based on program demands.",
        },
        "business": {
            "revenue_potential": f"Revenue projection at {avg:.0f}/100 — {'strong' if avg > 60 else 'developing'} market opportunity.",
            "failure_risk": f"Risk assessment at {avg:.0f}/100 — {'cautious' if avg > 60 else 'manageable'} failure probability.",
            "wealth_creation": f"Wealth creation potential at {avg:.0f}/100 — {'significant' if avg > 60 else 'moderate'} upside.",
        },
        "relocation": {
            "cost_of_living": f"Cost of living index at {avg:.0f}/100 — {'higher' if avg > 60 else 'manageable'} expense burden.",
            "quality_of_life": f"Quality of life at {avg:.0f}/100 — {'favourable' if avg > 60 else 'mixed'} outlook.",
        },
    }
    domain_templates = templates.get(domain_id, {})
    if node in domain_templates:
        return domain_templates[node]
    return f"{node.replace('_', ' ').title()} projected at {avg:.0f}/100."


def _build_events(agent_outputs: dict, all_causal: dict, anchors: dict | None = None) -> dict:
    """Generate deterministic life events per timeline. 0 LLM calls.
    Domain-aware: uses domain-specific event types and descriptions."""
    anchors = anchors or {}
    decision_type = anchors.get("_decision_type", "").lower()
    domain_id = get_domain(decision_type).value
    events = {}
    for tl_key in TIMELINE_KEYS:
        tl = all_causal.get(tl_key, {})
        tl_events = []
        for yr in YEARS:
            yr_scores = tl.get(yr, {})
            stress = yr_scores.get("stress", 50)
            health = yr_scores.get("health", 50)
            rel = yr_scores.get("relationships", 50)
            dom_events = _get_domain_events(domain_id, yr, yr_scores)
            tl_events.extend(dom_events)

            # Universal events shared across all domains
            if yr == "Year7" and rel > 60:
                tl_events.append({"year": yr, "type": "PERSONAL", "name": "Deepened Relationships", "description": "Strong support network established.", "impact": {"relationships": 5, "happiness": 4}})
            if yr == "Year10":
                score_summary = ", ".join(f"{k}: {v}" for k, v in sorted(yr_scores.items())[:3])
                tl_events.append({"year": yr, "type": "PERSONAL", "name": "Decade Milestone", "description": f"10-year milestone reached. Key scores: {score_summary}", "impact": {"happiness": 5}})
        events[tl_key] = tl_events
    return events


def _get_domain_events(domain_id: str, yr: str, scores: dict) -> list[dict]:
    stress = scores.get("stress", 50)
    events = []
    domain_event_map = {
        "education": [
            {"year": "Year1", "type": "ACADEMIC", "name": "Program Start", "cond": True, "desc": "Began academic program. Foundation year for core subjects.", "impact": {"learning_growth": 5, "academic_pressure": 3}},
            {"year": "Year3", "type": "ACADEMIC", "name": "Mid-Program Assessment", "cond": scores.get("learning_growth", 50) > 60, "desc": "Strong academic performance. Specialization options opening.", "impact": {"learning_growth": 8, "future_optionality": 5}},
            {"year": "Year5", "type": "OPPORTUNITY", "name": "Placement Window", "cond": scores.get("placement_potential", 50) > 60, "desc": "Major placement season — companies recruiting on campus.", "impact": {"placement_potential": 12, "future_optionality": 8}},
            {"year": "Year5", "type": "HEALTH", "name": "Academic Burnout Risk", "cond": stress > 65, "desc": "High stress period from exam/placement pressure.", "impact": {"health": -8, "academic_pressure": 5}},
        ],
        "business": [
            {"year": "Year1", "type": "MILESTONE", "name": "Launch", "cond": True, "desc": "Business launched. Initial product/market fit testing begins.", "impact": {"market_opportunity": 8, "stress": 5}},
            {"year": "Year3", "type": "MILESTONE", "name": "Traction Milestone", "cond": scores.get("revenue_potential", 50) > 55, "desc": "Revenue growing. Team expanding. Market validation achieved.", "impact": {"revenue_potential": 10, "wealth_creation": 8}},
            {"year": "Year5", "type": "FINANCIAL", "name": "Series A / Breakeven", "cond": scores.get("revenue_potential", 50) > 65, "desc": "Fundraising round closed or profitability achieved.", "impact": {"wealth_creation": 15, "burn_rate": -10}},
            {"year": "Year5", "type": "RISK", "name": "Cash Crunch Warning", "cond": scores.get("burn_rate", 50) > 65, "desc": "Burn rate exceeding projections. Cost management critical.", "impact": {"failure_risk": 10, "stress": 8}},
        ],
        "relocation": [
            {"year": "Year1", "type": "PERSONAL", "name": "Relocation Complete", "cond": True, "desc": "Moved to new location. Settlement and orientation phase.", "impact": {"cost_of_living": 5, "stress": 8}},
            {"year": "Year3", "type": "SOCIAL", "name": "Community Building", "cond": scores.get("social_support", 50) > 50, "desc": "New social network forming. Local connections strengthening.", "impact": {"social_support": 10, "quality_of_life": 5}},
            {"year": "Year5", "type": "CAREER", "name": "Local Career Breakthrough", "cond": scores.get("career_access", 50) > 60, "desc": "Career opportunities in new location materializing.", "impact": {"career_access": 12, "quality_of_life": 5}},
        ],
        "relationship": [
            {"year": "Year1", "type": "PERSONAL", "name": "Relationship Foundation", "cond": True, "desc": "Building the foundation of the relationship.", "impact": {"emotional_health": 5, "communication": 5}},
            {"year": "Year3", "type": "MILESTONE", "name": "Commitment Decision", "cond": scores.get("compatibility", 50) > 55, "desc": "Deepening commitment and shared future planning.", "impact": {"compatibility": 8, "future_alignment": 8}},
            {"year": "Year5", "type": "CHALLENGE", "name": "Relationship Stress Test", "cond": stress > 60, "desc": "External pressures testing relationship resilience.", "impact": {"stress": 5, "emotional_health": -5}},
        ],
        "financial": [
            {"year": "Year1", "type": "FINANCIAL", "name": "Initial Investment", "cond": True, "desc": "Financial plan initiated. Asset allocation established.", "impact": {"wealth_growth": 5, "cash_flow": 3}},
            {"year": "Year3", "type": "FINANCIAL", "name": "Portfolio Review", "cond": scores.get("wealth_growth", 50) > 55, "desc": "Portfolio showing compound growth. Rebalancing considered.", "impact": {"wealth_growth": 8, "financial_security": 5}},
            {"year": "Year5", "type": "FINANCIAL", "name": "Wealth Acceleration", "cond": scores.get("wealth_growth", 50) > 65, "desc": "Compound returns accelerating. Net worth growing significantly.", "impact": {"wealth_growth": 12, "financial_security": 8}},
        ],
        "health": [
            {"year": "Year1", "type": "HEALTH", "name": "Treatment Initiation", "cond": True, "desc": "Health treatment plan initiated. Monitoring phase begins.", "impact": {"treatment_efficacy": 5, "stress": 5}},
            {"year": "Year3", "type": "HEALTH", "name": "Recovery Assessment", "cond": scores.get("recovery_rate", 50) > 50, "desc": "Recovery progressing. Adjusting treatment protocol as needed.", "impact": {"recovery_rate": 8, "quality_of_life": 5}},
            {"year": "Year5", "type": "HEALTH", "name": "Stability Achieved", "cond": scores.get("quality_of_life", 50) > 60, "desc": "Condition stabilized. Long-term management plan in place.", "impact": {"quality_of_life": 10, "long_term_outlook": 8}},
        ],
        "lifestyle": [
            {"year": "Year1", "type": "PERSONAL", "name": "New Beginning", "cond": True, "desc": "Lifestyle change initiated. New routines forming.", "impact": {"fulfillment": 8, "stress": 5}},
            {"year": "Year3", "type": "MILESTONE", "name": "Finding Rhythm", "cond": scores.get("work_life_balance", 50) > 50, "desc": "New lifestyle rhythm established. Balance improving.", "impact": {"fulfillment": 8, "personal_growth": 5}},
        ],
    }
    domain_events = domain_event_map.get(domain_id, [])
    for de in domain_events:
        if de["year"] == yr and de["cond"]:
            events.append({"year": yr, "type": de["type"], "name": de["name"], "description": de["desc"], "impact": de["impact"]})
    return events


def _build_recommendation(analysis: dict, comparison: dict, anchors: dict | None = None) -> dict:
    """Deterministic recommendation from analysis. 0 LLM calls.
    Domain-aware: uses domain-specific weights and labels."""
    anchors = anchors or {}
    decision_type = anchors.get("_decision_type", "").lower()
    domain_id = get_domain(decision_type).value
    metrics = get_metrics_by_type(decision_type)
    arch_labels = _get_archetype_labels(decision_type)
    archetype_desc = _get_archetype_descriptions(decision_type)

    if not comparison:
        return {}
    best_score = -1
    best_tl = "Timeline B"

    for tl_key, data in comparison.items():
        if not isinstance(data, dict):
            continue
        # Use domain-weighted scoring
        weighted = 0
        total_weight = 0
        for node, w in metrics.weights.items():
            val = data.get(node, data.get("overall_score", 50))
            if isinstance(val, (int, float)):
                weighted += val * w
                total_weight += abs(w)
        score = weighted / max(total_weight, 0.01) if total_weight else data.get("overall_score", 50)
        if isinstance(score, (int, float)) and score > best_score:
            best_score = score
            best_tl = tl_key

    guardrails = _get_domain_guardrails(domain_id)
    triggers = _get_domain_triggers(domain_id)

    return {
        "primary_path": best_tl,
        "primary_label": arch_labels.get(best_tl, best_tl),
        "primary_archetype": archetype_desc.get(best_tl, ""),
        "reasoning": f"{arch_labels.get(best_tl, best_tl)} scores highest at {best_score:.0f}/100 based on {metrics.primary_metric} prioritization.",
        "domain": domain_id,
        "primary_metric": metrics.primary_metric,
        "guardrails": guardrails,
        "reassessment_triggers": triggers,
    }


def _get_domain_guardrails(domain_id: str) -> list[str]:
    guardrails = {
        "education": [
            "Reassess if academic performance drops by 15%",
            "Reassess if placement market changes significantly",
            "Reassess if personal interest in field shifts materially",
        ],
        "business": [
            "Reassess if burn rate exceeds projections by 30%",
            "Reassess if market conditions shift significantly",
            "Reassess if co-founder dynamics change",
        ],
        "relocation": [
            "Reassess if cost of living exceeds budget by 25%",
            "Reassess if visa/immigration status changes",
            "Reassess if quality of life expectations are not met",
        ],
        "relationship": [
            "Reassess if communication patterns become toxic",
            "Reassess if core values diverge significantly",
            "Reassess if emotional wellbeing consistently declines",
        ],
        "financial": [
            "Reassess if portfolio drops by more than 20%",
            "Reassess if interest rate environment shifts dramatically",
            "Reassess if liquidity needs change unexpectedly",
        ],
        "health": [
            "Reassess if treatment efficacy declines",
            "Reassess if new treatment options become available",
            "Reassess if quality of life is unacceptable",
        ],
        "lifestyle": [
            "Reassess if financial sustainability becomes a concern",
            "Reassess if isolation negatively impacts wellbeing",
            "Reassess if the lifestyle no longer aligns with values",
        ],
    }
    return guardrails.get(domain_id, [
        "Reassess if actual stress exceeds projected levels by 20%",
        "Reassess if external conditions change significantly",
        "Reassess if personal circumstances change significantly",
    ])


def _get_domain_triggers(domain_id: str) -> list[str]:
    triggers = {
        "education": ["Unexpected academic setback", "Major change in field interest", "Financial constraints change"],
        "business": ["Market downturn affecting runway", "Co-founder departure", "Regulatory change in industry"],
        "relocation": ["Visa denial or delay", "Family emergency requiring return", "Job market collapse in new location"],
        "relationship": ["Trust breakdown", "Life goal divergence", "Repeated conflict patterns"],
        "financial": ["Major market correction", "Job loss affecting cash flow", "Unexpected large expense"],
        "health": ["Treatment resistance develops", "New diagnosis or complication", "Support system changes"],
        "lifestyle": ["Financial runway running low", "Chronic loneliness or isolation", "Loss of passion for chosen path"],
    }
    return triggers.get(domain_id, [
        "Unexpected life event longer than 6 months",
        "Major health event",
        "Significant change in risk tolerance",
    ])


def _build_confidence_summary(agent_outputs: dict, data_confidence: float = 85, decision_type: str = "") -> dict:
    """Aggregate confidence from agent outputs. 0 LLM calls.
    Domain-aware: uses domain-specific agent names."""
    metrics = get_metrics_by_type(decision_type)
    agents_list = list(agent_outputs.keys()) if agent_outputs else metrics.nodes[:5]
    breakdown = {}
    total_conf = 0
    for name in agents_list:
        ao = agent_outputs.get(name, {})
        conf = ao.get("confidence", 0.7)
        breakdown[name] = {
            "confidence": round(conf * 100, 1),
            "label": name.replace("_", " ").title(),
        }
        total_conf += conf
    avg_agent = total_conf / len(agents_list) if agents_list else 0.7
    overall = 0.30 * (data_confidence / 100.0) + 0.25 * avg_agent + 0.25 * 0.70 + 0.20 * 0.75
    return {
        "overall": round(overall * 100, 1),
        "tier": "high" if overall >= 0.75 else "medium" if overall >= 0.50 else "low",
        "breakdown": breakdown,
        "components": {
            "agent_agreement": round(avg_agent * 100, 1),
            "data_quality": data_confidence,
            "historical_similarity": 72,
            "simulation_variance": 28,
            "data_freshness": 80,
        },
        "uncertainty_drivers": _get_uncertainty_drivers(avg_agent, data_confidence),
    }


def _get_uncertainty_drivers(agent_agreement: float, data_confidence: float) -> list:
    drivers = []
    if data_confidence < 60:
        drivers.append("Limited economic data quality reduces prediction reliability.")
    if agent_agreement < 0.6:
        drivers.append("Low agent agreement indicates genuine trade-off complexity.")
    if not drivers:
        drivers.append("High confidence across all dimensions.")
    return drivers


def _get_anchors(decision: str, context: dict, parsed) -> dict:
    """Build anchors with domain-specific enrichment. 0 LLM calls.
    Domain-aware: skips career grounding for non-career domains."""
    decision_type = getattr(parsed, "decision_type", "unknown")
    domain_id = get_domain(decision_type).value
    metrics = get_metrics_by_type(decision_type)

    # Domains that skip salary/macro data
    income_irrelevant = {"education", "relationship", "health", "lifestyle"}

    if domain_id in income_irrelevant:
        anchors = {
            "income_anchors": None,
            "opportunity_base": 50,
            "psychographic_bases": {"stress": 55, "health": 65, "relationships": 60, "happiness": 52},
            "prompt_block": f"{domain_id.upper()} DECISION: Domain-specific evaluation, no career grounding.",
            "salary_entry_lpa": None,
            "salary_mid_lpa": None,
            "salary_senior_lpa": None,
            "_computed": {},
            "_grounding": {},
            "_decision_type": decision_type,
            "_domain_id": domain_id,
        }
        logger.info(
            "[SimEngine] %s decision — no career grounding applied. type=%s",
            domain_id.title(), decision_type,
        )
        return anchors

    use_grounding = os.environ.get("USE_DATA_GROUNDING", "true").lower() == "true"
    if _GROUNDING_AVAILABLE and use_grounding:
        try:
            g = get_grounding_data(decision, context)
            anchors = build_score_anchors(g)
            cvars = compute_core_variables(g, context)
            anchors["_computed"] = cvars
            anchors["_grounding"] = g
            anchors["_decision_type"] = decision_type
            anchors["_domain_id"] = domain_id
            validate_simulation_input(anchors)
            logger.info(
                "[SimEngine] Decision type=%s domain=%s role=%s has_salary=%s",
                decision_type, domain_id,
                g.get("role", "unknown"),
                g.get("salary_entry_lpa") is not None,
            )
            return anchors
        except Exception as exc:
            logger.warning("[SimEngine] Grounding failed: %s — no fallback data available", exc)
            traceback.print_exc()

    return {
        "income_anchors": None,
        "opportunity_base": 50,
        "psychographic_bases": {"stress": 55, "health": 65, "relationships": 60, "happiness": 52},
        "prompt_block": "WARNING: No live data available.",
        "salary_entry_lpa": None,
        "salary_mid_lpa": None,
        "salary_senior_lpa": None,
        "_computed": {},
        "_grounding": {},
        "_decision_type": decision_type,
        "_domain_id": domain_id,
    }


def _build_enriched_timelines(all_causal: dict, anchors: dict) -> dict:
    """Build enriched timeline dicts with template narratives."""
    enriched = {}
    dt = anchors.get("_decision_type", "unknown")

    for tl_key in TIMELINE_KEYS:
        causal = all_causal.get(tl_key, {})

        narratives = _build_narratives(causal, anchors, tl_key=tl_key)
        interps = build_score_interpretations(causal, anchors)

        enriched[tl_key] = {
            **narratives,
            "_causal": causal,
            "_interpretations": interps,
            "_grounding": anchors.get("_grounding", {}),
            "_computed": anchors.get("_computed", {}),
            "_decision_type": dt,
        }

    enriched["_analysis"] = _build_analysis(enriched, anchors, {})
    return enriched


def _build_analysis(timelines: dict, anchors: dict, context: dict) -> dict:
    """Deterministic decision analysis. 0 LLM calls.
    Domain-aware: uses domain-specific analysis templates."""
    cvars = anchors.get("_computed", {})
    grounding = anchors.get("_grounding", {})
    decision_type = anchors.get("_decision_type", "").lower()
    domain_id = get_domain(decision_type).value
    metrics = get_metrics_by_type(decision_type)

    location = grounding.get("location", "India")
    stress = cvars.get("stress_score", 50)
    options = context.get("options", context.get("fields", []))
    institution = context.get("institution", "college")
    role = grounding.get("role", "unknown")

    analysis_templates = {
        "education": lambda: {
            "summary": {
                "domain": "Education",
                "focus": f"Educational path in {location}.",
                "key_metrics": ", ".join(metrics.nodes[:4]),
                "description": f"Pursuing {', '.join(options) if options else 'academic program'} at {institution}." if institution else f"Pursuing {', '.join(options) if options else 'academic program'}.",
                "stress_level": f"Academic stress at {stress}/100.",
            },
            "five_year_outlook": "Graduation and early-career phase. Placement outcomes and higher studies options shape long-term trajectory.",
            "tradeoffs": {
                "gained": f"Degree from {institution or 'program'} opens pathways in {grounding.get('industry', 'professional')} sector.",
                "sacrificed": f"Stress {stress}/100 reflects academic and placement pressure.",
            },
            "scenario_shifts": {
                "strong_placement": "Robust placement outcomes accelerate career launch.",
                "weak_market": "Economic downturn may delay graduate hiring.",
                "higher_studies": "Pursuing postgraduate options expands career optionality.",
            },
        },
        "business": lambda: {
            "summary": {
                "domain": "Business",
                "focus": f"Entrepreneurial venture in {grounding.get('industry', 'technology')}.",
                "key_metrics": ", ".join(metrics.nodes[:4]),
                "description": f"Building a business with focus on market opportunity and sustainable growth.",
                "stress_level": f"Entrepreneurial stress at {stress}/100.",
            },
            "five_year_outlook": "Growth trajectory depends on product-market fit, funding access, and team execution.",
            "tradeoffs": {
                "gained": "Full ownership, unlimited upside, and direct market impact.",
                "sacrificed": f"Stress {stress}/100, income volatility, and personal time investment.",
            },
            "scenario_shifts": {
                "strong_funding": "Successful fundraising accelerates hiring and scale.",
                "market_downturn": "Capital becomes scarce, pivots may be necessary.",
                "slow_traction": "Burn rate management becomes critical for survival.",
            },
        },
        "relocation": lambda: {
            "summary": {
                "domain": "Relocation",
                "focus": f"Relocation to {location or 'new location'}.",
                "key_metrics": ", ".join(metrics.nodes[:4]),
                "description": "Transitioning to a new environment with focus on quality of life and career access.",
                "stress_level": f"Relocation stress at {stress}/100.",
            },
            "five_year_outlook": "Settlement phase transitions to integration and community building over 3-5 years.",
            "tradeoffs": {
                "gained": f"Access to new opportunities and improved quality of life in {location or 'new location'}.",
                "sacrificed": f"Leaving existing support networks and familiar environment. Stress {stress}/100.",
            },
            "scenario_shifts": {
                "strong_integration": "Rapid community building accelerates settlement.",
                "visa_difficulties": "Immigration challenges delay full integration.",
                "culture_shock": "Extended adjustment period impacts wellbeing initially.",
            },
        },
        "relationship": lambda: {
            "summary": {
                "domain": "Relationship",
                "focus": "Relationship development and partnership.",
                "key_metrics": ", ".join(metrics.nodes[:4]),
                "description": "Navigating relationship dynamics with focus on emotional health and compatibility.",
                "stress_level": f"Relationship stress at {stress}/100.",
            },
            "five_year_outlook": "Relationship deepens through shared experiences, communication, and alignment on life goals.",
            "tradeoffs": {
                "gained": "Emotional support, shared growth, and partnership.",
                "sacrificed": f"Individual autonomy in certain areas. Stress {stress}/100 from relationship work.",
            },
            "scenario_shifts": {
                "strong_communication": "Open dialogue resolves conflicts before they compound.",
                "life_goal_divergence": "Different priorities may require difficult conversations.",
                "external_pressure": "Career or family stress tests relationship resilience.",
            },
        },
        "financial": lambda: {
            "summary": {
                "domain": "Financial",
                "focus": "Financial strategy and wealth management.",
                "key_metrics": ", ".join(metrics.nodes[:4]),
                "description": "Managing financial resources with focus on growth, security, and liquidity.",
                "stress_level": f"Financial stress at {stress}/100.",
            },
            "five_year_outlook": "Compound returns accelerate wealth accumulation after Year 5 if strategy remains disciplined.",
            "tradeoffs": {
                "gained": "Financial security, wealth growth, and optionality.",
                "sacrificed": f"Short-term liquidity for long-term growth. Stress {stress}/100 from market exposure.",
            },
            "scenario_shifts": {
                "bull_market": "Above-average returns accelerate financial independence timeline.",
                "bear_market": "Portfolio drawdown tests risk tolerance and discipline.",
                "inflation_spike": "Purchasing power erosion requires strategy adjustment.",
            },
        },
        "health": lambda: {
            "summary": {
                "domain": "Health",
                "focus": "Health treatment and wellness journey.",
                "key_metrics": ", ".join(metrics.nodes[:4]),
                "description": "Navigating health decisions with focus on treatment efficacy and quality of life.",
                "stress_level": f"Health-related stress at {stress}/100.",
            },
            "five_year_outlook": "Recovery and management trajectory depends on treatment adherence and support system strength.",
            "tradeoffs": {
                "gained": "Improved health outcomes and long-term wellbeing.",
                "sacrificed": f"Treatment side effects and lifestyle adjustments. Stress {stress}/100.",
            },
            "scenario_shifts": {
                "strong_response": "Positive treatment response accelerates recovery timeline.",
                "complications": "Unexpected complications require protocol adjustments.",
                "lifestyle_change": "Lifestyle modifications compound treatment benefits.",
            },
        },
        "lifestyle": lambda: {
            "summary": {
                "domain": "Lifestyle",
                "focus": "Lifestyle transformation and personal fulfillment.",
                "key_metrics": ", ".join(metrics.nodes[:4]),
                "description": "Pursuing a lifestyle aligned with personal values and fulfillment.",
                "stress_level": f"Lifestyle stress at {stress}/100.",
            },
            "five_year_outlook": "New routines solidify into sustainable lifestyle within 3 years if financial foundations hold.",
            "tradeoffs": {
                "gained": "Authentic living, personal fulfillment, and freedom.",
                "sacrificed": f"Financial certainty and social conformity. Stress {stress}/100 from uncertainty.",
            },
            "scenario_shifts": {
                "financial_sustainability": "Side income streams stabilize the unconventional path.",
                "social_isolation": "Lack of peer alignment may create loneliness over time.",
                "passion_to_profession": "Personal passion successfully monetized.",
            },
        },
    }

    if domain_id in analysis_templates:
        return analysis_templates[domain_id]()

    # Fallback for career and general
    if not cvars:
        return {}

    salary_lpa = cvars.get("expected_salary_lpa")
    monthly_inc = cvars.get("monthly_income", 0)
    expenses = cvars.get("monthly_expenses", 0)
    disposable = cvars.get("disposable_income", 0)
    savings_rate = cvars.get("savings_rate_pct", 0)
    unemp = grounding.get("live_unemployment")
    cpi = grounding.get("live_cpi")
    gdp = grounding.get("live_gdp_growth")

    unemp_text = _fmt_pct(unemp)
    gdp_text = _fmt_pct(gdp)
    cpi_text = _fmt_pct(cpi)
    market_text = "stable" if unemp is not None and unemp < 6 else "uncertain"
    disp_sign = "+" if disposable >= 0 else ""
    return {
        "summary": {
            "domain": "Career",
            "path": f"{role.title()} in {location}.",
            "financial_situation": (
                f"Earning \u20b9{_fmt_safe(salary_lpa, '.1f')} LPA (\u20b9{monthly_inc:,}/month). "
                f"Expenses \u20b9{expenses:,}/month, disposable {disp_sign}\u20b9{disposable:,}/month."
            ),
            "stress_level": f"Computed stress {stress}/100.",
            "savings_potential": f"Savings rate {savings_rate}% of monthly income.",
        },
        "five_year_outlook": (
            f"With \u20b9{disposable:,}/month disposable, savings are "
            f"{'feasible' if disposable > 0 else 'constrained'}. "
            f"Unemployment {unemp_text}, GDP {gdp_text} — "
            f"{market_text} job market. "
            f"CPI {cpi_text} erodes purchasing power over time."
        ),
        "tradeoffs": {
            "gained": f"Stable \u20b9{_fmt_safe(salary_lpa, '.1f')} LPA in {grounding.get('industry', 'professional')} sector.",
            "sacrificed": f"Stress {stress}/100 reflects ongoing professional pressure.",
        },
        "scenario_shifts": {
            "higher_salary": "Higher salary increases disposable income and reduces financial stress.",
            "lower_salary": "Lower salary may push disposable income negative given current expense levels.",
            "economic_downturn": "Rising unemployment or GDP contraction would reduce opportunity and increase stress.",
        },
    }


def make_option_comparison(
    decision: str,
    context: dict,
    parsed=None,
) -> dict:
    """
    Direct option-to-option comparison (e.g. CSE vs AIML).

    This is an alternative to the 3-timeline archetype model.
    It generates a single projection per option and compares them
    across dimensions.  0 LLM calls.

    Returns
    -------
    dict with:
      options: [str, str]
      profiles: [{name, scores}]
      winner: str
      reason: str
      confidence: int
      dimension_scores: {option: {dimension: score}}
    """
    if parsed is None:
        parsed = parse_decision(decision)
    options = parsed.options
    decision_type = parsed.decision_type

    if len(options) < 2:
        return {
            "options": options,
            "winner": options[0] if options else "N/A",
            "reason": "Single option — no comparison needed.",
            "confidence": 100,
            "profiles": [],
            "dimension_scores": {},
        }

    profiles_data = []
    for opt in options:
        profile = get_profile_or_default(opt, decision_type)
        profile = _validate_profile_before_use(profile, f"option:{opt}")
        scores = profile_to_scores(profile)
        profiles_data.append({
            "name": opt,
            "profile": profile,
            "scores": scores,
        })

    weighted = _score_options(profiles_data, decision_type)
    ranked = sorted(weighted.items(), key=lambda x: x[1]["total"], reverse=True)
    winner = ranked[0][0] if ranked else options[0]

    dim_scores = {}
    for pd in profiles_data:
        dim_scores[pd["name"]] = pd["scores"]

    salary_diff = None
    risk_diff = None
    if len(weighted) >= 2:
        s0 = weighted[options[0]].get("scores", {})
        s1 = weighted[options[1]].get("scores", {})
        salary_diff = abs(s0.get("income", 50) - s1.get("income", 50)) // 5
        risk_diff = abs(s0.get("stress", 50) - s1.get("stress", 50)) // 5

    winner_profile = next((pd for pd in profiles_data if pd["name"] == winner), None)
    if winner_profile:
        ws = winner_profile["scores"]
        income_desc = "high" if ws["income"] >= 70 else "moderate" if ws["income"] >= 45 else "lower"
        risk_desc = "higher risk" if ws["stress"] >= 60 else "balanced risk" if ws["stress"] >= 45 else "lower risk"
        reason = (
            f"{winner} scores higher in salary potential and opportunity "
            f"with {income_desc} income trajectory ({income_desc}) "
            f"and {risk_desc} profile."
        )
        confidence = 85
    else:
        reason = f"{winner} is the recommended option based on multi-dimensional scoring."
        confidence = 75

    if salary_diff is not None:
        reason += f" Salary difference ~\u20b9{salary_diff} LPA by Year 10."

    return {
        "options": options,
        "winner": winner,
        "reason": reason,
        "confidence": confidence,
        "profiles": profiles_data,
        "dimension_scores": dim_scores,
        "decision_type": decision_type,
    }


def _score_options(profiles_data: list, decision_type: str = "") -> dict:
    """Weighted multi-dimensional scoring of options.
    Domain-aware: uses domain-specific weights."""
    metrics = get_metrics_by_type(decision_type)
    weights = metrics.weights

    result = {}
    for pd in profiles_data:
        scores = pd["scores"]
        scores = _validate_profile_before_use(scores, "scores")
        raw_total = 50.0
        for node, w in weights.items():
            val = scores.get(node, 50)
            raw_total += (val - 50) * w
        total = max(0, min(100, raw_total))
        result[pd["name"]] = {
            "total": round(total, 1),
            "scores": scores,
        }
    return result
