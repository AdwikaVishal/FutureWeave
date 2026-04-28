"""
Chaos Agent — deterministic structured random events. No LLM call.

Uses a weighted event library keyed by timeline personality so events
feel differentiated without consuming any quota.
"""
import random
from typing import Optional

NODES = ["income", "career_growth", "stress", "health", "relationships", "happiness", "opportunity"]
YEARS = ["Year1", "Year3", "Year5", "Year10"]

# Event library — keyed by personality ("A"=conservative, "B"=balanced, "C"=aggressive)
_EVENT_LIBRARY: dict[str, list[dict]] = {
    "A": [
        {"year": "Year3",  "name": "Steady Promotion",
         "description": "Consistent performance earns a structured promotion.",
         "node_deltas": {"income": +8, "career_growth": +10, "stress": +5}},
        {"year": "Year5",  "name": "Health Scare",
         "description": "A brief illness prompts a lifestyle reassessment.",
         "node_deltas": {"health": -12, "stress": +8, "relationships": +6}},
        {"year": "Year10", "name": "Stable Milestone",
         "description": "A decade of steady work yields financial security.",
         "node_deltas": {"happiness": +10, "income": +5, "stress": -8}},
    ],
    "B": [
        {"year": "Year3",  "name": "Economic Slowdown",
         "description": "A market correction reduces hiring in your sector.",
         "node_deltas": {"income": -8, "stress": +12, "opportunity": -10}},
        {"year": "Year5",  "name": "Unexpected Mentor",
         "description": "A senior leader takes interest in your career.",
         "node_deltas": {"career_growth": +15, "opportunity": +12, "happiness": +8}},
        {"year": "Year10", "name": "Industry Disruption",
         "description": "New technology reshapes your field — adapt or fall behind.",
         "node_deltas": {"career_growth": -8, "stress": +10, "opportunity": +18}},
    ],
    "C": [
        {"year": "Year3",  "name": "High-Stakes Bet",
         "description": "An aggressive move pays off — or doesn't.",
         "node_deltas": {"income": +20, "stress": +20, "health": -10}},
        {"year": "Year5",  "name": "Burnout Episode",
         "description": "The pace catches up — a forced slowdown.",
         "node_deltas": {"health": -20, "stress": +15, "happiness": -12, "relationships": -8}},
        {"year": "Year10", "name": "Lucky Break",
         "description": "A chance connection opens a major opportunity.",
         "node_deltas": {"opportunity": +20, "career_growth": +12, "happiness": +10}},
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
