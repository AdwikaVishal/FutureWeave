"""
Event Engine Agent — generates macro, industry, personal, health, and opportunity events.
Replaces the old Chaos Agent with structured, causally-connected event generation.
"""
import json
import logging
import random
from typing import Any, Dict, List, Optional

from .llm_agent import LLMAgent
from quota_manager import get_quota_manager

logger = logging.getLogger(__name__)

TIMELINE_KEYS = ["Timeline A", "Timeline B", "Timeline C"]

_EVENT_LIBRARY = {
    "Timeline A": [
        {"year": "Year3", "type": "PERSONAL", "name": "Community Anchor", "description": "Deep local network forms around shared projects.", "impact": {"income": 0, "stress": -8, "health": 3, "relationships": 12, "career_growth": 4}, "probability": 0.7},
        {"year": "Year5", "type": "HEALTH", "name": "Health Reassessment", "description": "Routine check-up prompts lifestyle changes.", "impact": {"income": 0, "stress": 5, "health": -8, "relationships": 0, "career_growth": 0}, "probability": 0.5},
        {"year": "Year7", "type": "OPPORTUNITY", "name": "Stability Dividend", "description": "Tenure and reputation create unexpected opportunities.", "impact": {"income": 8, "stress": -5, "health": 0, "relationships": 5, "career_growth": 10}, "probability": 0.6},
        {"year": "Year10", "type": "PERSONAL", "name": "Quiet Milestone", "description": "A decade of consistency pays off in financial security.", "impact": {"income": 6, "stress": -10, "health": 3, "relationships": 8, "career_growth": 5}, "probability": 0.8},
    ],
    "Timeline B": [
        {"year": "Year2", "type": "INDUSTRY", "name": "Promotion Passed Over", "description": "External hire takes the role you wanted.", "impact": {"income": -3, "stress": 12, "health": -3, "relationships": 0, "career_growth": -5}, "probability": 0.4},
        {"year": "Year4", "type": "OPPORTUNITY", "name": "Strategic Sponsor", "description": "Senior leader advocates for your next move.", "impact": {"income": 10, "stress": -3, "health": 0, "relationships": 0, "career_growth": 15}, "probability": 0.5},
        {"year": "Year6", "type": "MACRO_ECONOMIC", "name": "Market Correction", "description": "Economic slowdown tests your strategy.", "impact": {"income": -8, "stress": 15, "health": -5, "relationships": 0, "career_growth": -3}, "probability": 0.6},
        {"year": "Year8", "type": "INDUSTRY", "name": "Tech Shift", "description": "Automation reshapes your sector.", "impact": {"income": 5, "stress": 8, "health": 0, "relationships": 0, "career_growth": 12}, "probability": 0.5},
        {"year": "Year10", "type": "INDUSTRY", "name": "Industry Pivot", "description": "Skills investment pays off as sector transforms.", "impact": {"income": 15, "stress": 3, "health": 0, "relationships": 0, "career_growth": 18}, "probability": 0.5},
    ],
    "Timeline C": [
        {"year": "Year2", "type": "OPPORTUNITY", "name": "Big Bet", "description": "High-risk opportunity materializes.", "impact": {"income": 22, "stress": 15, "health": -8, "relationships": -6, "career_growth": 18}, "probability": 0.4},
        {"year": "Year4", "type": "HEALTH", "name": "Burnout Warning", "description": "Body forces a slowdown.", "impact": {"income": -5, "stress": 18, "health": -22, "relationships": -8, "career_growth": -3}, "probability": 0.5},
        {"year": "Year6", "type": "PERSONAL", "name": "Relationship Cost", "description": "A key relationship ends due to lifestyle.", "impact": {"income": 0, "stress": 15, "health": -5, "relationships": -20, "career_growth": 3}, "probability": 0.4},
        {"year": "Year8", "type": "OPPORTUNITY", "name": "Breakout", "description": "Major career breakthrough validates the gambler path.", "impact": {"income": 28, "stress": 5, "health": 0, "relationships": 5, "career_growth": 22}, "probability": 0.25},
        {"year": "Year10", "type": "MACRO_ECONOMIC", "name": "Reckoning", "description": "The decade's bet resolves decisively.", "impact": {"income": 15, "stress": 10, "health": -3, "relationships": -5, "career_growth": 12}, "probability": 0.5},
    ],
}

_SHARED_EVENTS = [
    {"year": "Year3", "type": "PERSONAL", "name": "Family Event", "description": "A family milestone changes priorities.", "impact": {"income": 0, "stress": 8, "health": 0, "relationships": 10, "career_growth": -2}, "probability": 0.6},
    {"year": "Year5", "type": "MACRO_ECONOMIC", "name": "Economic Cycle", "description": "Broad economic shift affects everyone.", "impact": {"income": -8, "stress": 12, "health": 0, "relationships": 0, "career_growth": -5}, "probability": 0.7},
]


class EventEngineAgent(LLMAgent):
    def __init__(self):
        super().__init__("event_engine", "event_engine.txt", temperature=0.7)

    def generate_events(
        self,
        decision: str,
        context: dict,
        economic_data: dict,
    ) -> dict:
        qm = get_quota_manager()
        if not qm.should_use_llm("event_engine"):
            logger.info("[EventEngine] Quota mode '%s' — using library fallback", qm.mode)
            return self._library_fallback()

        gdp = economic_data.get("gdp_growth")
        ind_health = economic_data.get("industry_health")
        auto_risk = economic_data.get("automation_risk")
        if gdp is None:
            logger.warning("[EventEngine] gdp_growth not available from live data")
        if ind_health is None:
            logger.warning("[EventEngine] industry_health not available from live data")
        if auto_risk is None:
            logger.warning("[EventEngine] automation_risk not available from live data")

        prompt = self.build_prompt(
            decision=decision,
            context=json.dumps(context, indent=2, default=str),
            gdp_growth=gdp,
            industry_health=ind_health,
            automation_risk=auto_risk,
            location=context.get("location", "India"),
            role=context.get("role", "unknown"),
        )

        try:
            result = self.run_structured(prompt)
            if "events" not in result:
                raise ValueError("Missing 'events' key")
            return result
        except Exception as exc:
            logger.warning("[EventEngine] LLM failed: %s — using library fallback", exc)
            return self._library_fallback()

    def _library_fallback(self) -> dict:
        events: Dict[str, list] = {}
        for tl_key in TIMELINE_KEYS:
            tl_events = []
            pool = _EVENT_LIBRARY.get(tl_key, [])
            for event in pool:
                if random.random() < event["probability"]:
                    tl_events.append(event)
            shared = random.choice(_SHARED_EVENTS) if random.random() < 0.4 else None
            if shared:
                tl_events.append(shared)
            events[tl_key] = sorted(tl_events, key=lambda e: e["year"])
        return {"events": events}

    def apply_events(self, events: List[dict], scores: dict) -> dict:
        result = dict(scores)
        for event in events:
            impact = event.get("impact", {})
            for metric, delta in impact.items():
                if metric in result:
                    new_val = result.get(metric, 50) + delta
                    if metric == "income" and new_val < 5:
                        logger.warning(
                            "[EventEngine] Event '%s' would set income=%.1f (delta=%+.1f) — clamping to 5",
                            event.get("name", "unknown"), new_val, delta,
                        )
                        new_val = 5
                    result[metric] = max(0, min(100, new_val))
        return result
