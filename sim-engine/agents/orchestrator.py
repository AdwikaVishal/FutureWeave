"""
Orchestrator Agent

Coordinates all specialist agents. Never generates final simulations.

Responsibilities:
  1. Understand the user's decision.
  2. Determine which specialist agents to invoke.
  3. Pass relevant context to each agent.
  4. Collect their outputs.
  5. Detect disagreements between agents.
  6. Forward conflicts to the Debate Agent.
  7. Send consolidated data to the Timeline Agent.

Always returns structured JSON. Never assumes without evidence.
Always preserves uncertainty and includes confidence scores.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from agents.decision_analysis import analyze_decision
from agents.economic_research import collect_economic_research

logger = logging.getLogger(__name__)

# ── Agent registry ────────────────────────────────────────────────────────────

# Maps decision_type → required specialist agents
_AGENT_REGISTRY: dict[str, list[str]] = {
    "Career Pivot":      ["decision_analysis", "economic_research", "timeline"],
    "Startup vs Job":    ["decision_analysis", "economic_research", "chaos", "timeline"],
    "Relocation":        ["decision_analysis", "economic_research", "timeline"],
    "Higher Education":  ["decision_analysis", "economic_research", "timeline"],
    "Relationship":      ["decision_analysis", "timeline"],
    "Financial":         ["decision_analysis", "economic_research", "timeline"],
    "Other":             ["decision_analysis", "timeline"],
}

# Nodes where disagreements are expected and require debate
_CONFLICT_THRESHOLD = 25  # score-point delta that triggers a conflict


# ── Conflict detection ────────────────────────────────────────────────────────

def _detect_conflicts(decision_profile: dict, economic_data: dict | None) -> list[dict]:
    """
    Compare decision_analysis risk_tolerance against economic_data confidence.
    Returns a list of conflict descriptors (empty = no disagreements).
    """
    conflicts: list[dict] = []

    if economic_data is None:
        return conflicts

    econ_confidence = economic_data.get("confidence", 100)
    risk = decision_profile.get("risk_tolerance", "Medium").lower()

    # High risk + low economic data confidence = factual basis conflict
    if risk == "high" and econ_confidence < 50:
        conflicts.append({
            "type": "evidence_gap",
            "agents": ["decision_analysis", "economic_research"],
            "description": (
                f"Decision profile indicates high risk tolerance but economic data "
                f"confidence is only {econ_confidence}%. "
                "Projections may be speculative."
            ),
            "severity": "high",
        })

    missing = economic_data.get("missing_data", [])
    if len(missing) >= 4:
        conflicts.append({
            "type": "data_scarcity",
            "agents": ["economic_research"],
            "description": (
                f"{len(missing)} of 8 economic sources are unavailable. "
                "Timeline projections carry elevated uncertainty."
            ),
            "severity": "medium",
        })

    return conflicts


# ── Key factor extraction ─────────────────────────────────────────────────────

def _extract_key_factors(
    decision_profile: dict,
    economic_data: dict | None,
    context: dict,
) -> list[str]:
    factors: list[str] = []

    # From decision analysis
    if kw := decision_profile.get("keywords"):
        factors.extend(kw[:4])
    if goal := decision_profile.get("core_goal"):
        factors.append(goal)
    if fear := decision_profile.get("biggest_fear"):
        factors.append(fear)

    # From economic data
    if economic_data:
        sg = economic_data.get("salary_growth", {})
        if sr := sg.get("salary_range_lpa"):
            factors.append(f"Salary range: ₹{sr[0]}–{sr[1]} LPA")
        ft = economic_data.get("future_trends", {})
        for signal in ft.get("signals", [])[:2]:
            factors.append(signal)

    # From user context
    if loc := context.get("location"):
        factors.append(f"Location: {loc}")
    if age := context.get("age"):
        factors.append(f"Age: {age}")

    return list(dict.fromkeys(factors))  # deduplicate, preserve order


# ── Confidence roll-up ────────────────────────────────────────────────────────

def _rollup_confidence(decision_profile: dict, economic_data: dict | None, conflicts: list[dict]) -> int:
    base = 80  # orchestrator starts at 80 — not all inputs are verified

    # Penalise for low economic confidence
    if economic_data:
        econ_conf = economic_data.get("confidence", 100)
        base = min(base, econ_conf)

    # Penalise each conflict
    for c in conflicts:
        base -= 10 if c["severity"] == "high" else 5

    return max(0, min(100, base))


# ── Debate stub ───────────────────────────────────────────────────────────────

def _forward_to_debate(conflicts: list[dict]) -> dict:
    """
    Placeholder: forward conflicts to the Debate Agent.
    When a real DebateAgent exists, replace this body with the actual call.
    """
    if not conflicts:
        return {"debate_required": False, "resolutions": []}

    logger.warning("[Orchestrator] %d conflict(s) forwarded to Debate Agent", len(conflicts))
    return {
        "debate_required": True,
        "conflicts": conflicts,
        "resolutions": [],  # populated by DebateAgent when implemented
        "note": "Debate Agent not yet implemented — conflicts logged, uncertainty preserved.",
    }


# ── Main orchestration ────────────────────────────────────────────────────────

async def orchestrate(
    decision: str,
    context: dict,
) -> dict[str, Any]:
    """
    Coordinate all specialist agents for a given decision.

    Args:
        decision:  Raw decision text from the user.
        context:   User demographics dict (age, location, risk_tolerance, …).

    Returns:
        Structured orchestration result — never a final simulation.
    """
    location     = context.get("location", "India")
    career_stage = context.get("career_stage", "mid-career")

    # ── Step 1: Decision Analysis ─────────────────────────────────────────────
    logger.info("[Orchestrator] Running decision_analysis")
    decision_profile = analyze_decision(decision, context, location, career_stage)
    decision_type    = decision_profile.get("decision_type", "Other")

    # ── Step 2: Determine required agents ────────────────────────────────────
    required_agents = _AGENT_REGISTRY.get(decision_type, _AGENT_REGISTRY["Other"])

    # ── Step 3 & 4: Collect economic data (if needed) ─────────────────────────
    economic_data: dict | None = None
    if "economic_research" in required_agents:
        logger.info("[Orchestrator] Running economic_research")
        economic_data = await collect_economic_research(decision, context)

    # ── Step 5: Detect conflicts ──────────────────────────────────────────────
    conflicts = _detect_conflicts(decision_profile, economic_data)

    # ── Step 6: Forward to Debate Agent ──────────────────────────────────────
    debate_result = _forward_to_debate(conflicts)

    # ── Step 7: Build consolidated payload for Timeline Agent ─────────────────
    key_factors = _extract_key_factors(decision_profile, economic_data, context)
    confidence  = _rollup_confidence(decision_profile, economic_data, conflicts)

    logger.info(
        "[Orchestrator] decision_type=%s agents=%s confidence=%d conflicts=%d",
        decision_type, required_agents, confidence, len(conflicts),
    )

    return {
        "decision_type":     decision_type,
        "required_agents":   required_agents,
        "key_factors":       key_factors,
        "confidence":        confidence,
        # ── Full agent outputs (consumed by Timeline Agent) ──────────────────
        "agent_outputs": {
            "decision_analysis": decision_profile,
            "economic_research": economic_data,
        },
        # ── Conflict handling ────────────────────────────────────────────────
        "conflicts":          conflicts,
        "debate":             debate_result,
        # ── Metadata ─────────────────────────────────────────────────────────
        "uncertainty_flags": [c["description"] for c in conflicts],
    }


def _run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()


def run_orchestrator(decision: str, context: dict) -> dict:
    """Synchronous entry point (wraps the async orchestrate call)."""
    return _run_sync(orchestrate(decision, context))
