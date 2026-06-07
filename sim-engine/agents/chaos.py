"""
Chaos Agent — deterministic structured random events. No LLM call.

Uses a weighted event library keyed by timeline personality so events
feel differentiated without consuming any quota.
"""
import random
from typing import Optional

NODES = ["income", "career_growth", "stress", "health", "relationships", "happiness", "opportunity"]
YEARS = ["Year1", "Year3", "Year5", "Year10"]

# Event library — keyed by personality ("A"=Settler, "B"=Climber, "C"=Gambler)
_EVENT_LIBRARY: dict[str, list[dict]] = {
    "A": [
        {"year": "Year3",  "name": "Community Anchor",
         "description": "A deep local network forms around shared projects and friendships.",
         "node_deltas": {"relationships": +12, "happiness": +8, "opportunity": +4}},
        {"year": "Year5",  "name": "Health Reassessment",
         "description": "A routine check-up surfaces a manageable issue — prompts lifestyle changes.",
         "node_deltas": {"health": -10, "stress": +7, "relationships": +6}},
        {"year": "Year10", "name": "Quiet Milestone",
         "description": "A decade of consistency pays off: financial security, trusted relationships.",
         "node_deltas": {"happiness": +12, "stress": -10, "income": +6}},
    ],
    "B": [
        {"year": "Year3",  "name": "Promotion Passed Over",
         "description": "A promised promotion goes to an external hire — a recalibration moment.",
         "node_deltas": {"career_growth": -8, "stress": +14, "opportunity": +10}},
        {"year": "Year5",  "name": "Strategic Sponsor",
         "description": "A senior leader actively advocates for your next role.",
         "node_deltas": {"career_growth": +15, "income": +10, "opportunity": +12}},
        {"year": "Year10", "name": "Industry Pivot",
         "description": "Automation reshapes your sector — skills investment pays off or falls short.",
         "node_deltas": {"career_growth": -6, "stress": +10, "opportunity": +20}},
    ],
    "C": [
        {"year": "Year3",  "name": "High-Stakes Outcome",
         "description": "The big bet resolves — a large upside or a hard reset.",
         "node_deltas": {"income": +22, "stress": +18, "health": -10, "relationships": -8}},
        {"year": "Year5",  "name": "Burnout Crash",
         "description": "The pace forces a stop. A month off, health consequences, a relationship ends.",
         "node_deltas": {"health": -22, "stress": +16, "happiness": -14, "relationships": -10}},
        {"year": "Year10", "name": "Breakout or Reckoning",
         "description": "The decade resolves decisively — a major win or the cost becomes undeniable.",
         "node_deltas": {"opportunity": +22, "income": +15, "happiness": +12}},
    ],
}

_SHARED_EVENTS = [
    {"year": "Year3",  "name": "Family Emergency",
     "description": "An unexpected family situation demands time and money.",
     "node_deltas": {"stress": +15, "relationships": +8, "income": -5, "happiness": -8}},
    {"year": "Year5",  "name": "Market Crash",
     "description": "A broad economic downturn affects savings and job security.",
     "node_deltas": {"income": -12, "stress": +18, "opportunity": -15}},
]


def apply_chaos(causal_scores: dict, personality_key: Optional[str] = None) -> dict:
    """
    Return 1–2 structured chaos events. No LLM call.

    causal_scores   : Year1 scores dict (kept for API compatibility)
    personality_key : "A", "B", or "C" — defaults to "B"
    """
    pk     = personality_key or "B"
    pool   = _EVENT_LIBRARY.get(pk, _EVENT_LIBRARY["B"])

    chosen = [random.choice(pool)]
    if random.random() < 0.4:   # 40% chance of a second shared event
        chosen.append(random.choice(_SHARED_EVENTS))

    return {"events": chosen}
