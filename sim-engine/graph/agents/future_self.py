"""
Future Self Agent — generates living personas for each timeline that can answer follow-up questions.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from .llm_agent import LLMAgent
from quota_manager import get_quota_manager

logger = logging.getLogger(__name__)

_BATCH_PROMPT_TEMPLATE = """You are generating three Future Self personas for someone facing this decision:

DECISION: {decision}
CONTEXT: {context}

Each persona represents who they become 10 years after choosing a specific path.

Generate a JSON object with keys "Timeline A", "Timeline B", "Timeline C".
Each value should have:
- "name": A first name only (different for each timeline)
- "age": {age}
- "occupation": A realistic job title consistent with the archetype
- "location": A realistic city in India
- "biography": A 2-3 sentence reflection on their decade
- "personality_traits": 3 traits as a list
- "core_values": 3 values as a list
- "biggest_lesson": One sentence
- "biggest_regret": One sentence
- "proudest_moment": One sentence
- "current_challenges": 1-2 challenges as a list
- "advice_to_past_self": One sentence
- "perspectives": An object with keys on_risk, on_career, on_relationships, on_health, on_money, on_the_path_not_taken
- "voice_style": "reflective", "pragmatic", or "intense"

Make each persona feel distinct and authentic to their archetype."""


class FutureSelfAgent(LLMAgent):
    def __init__(self):
        super().__init__("future_self", "future_self.txt", temperature=0.8)

    def create_persona(
        self,
        timeline_label: str,
        archetype: str,
        timeline_data: dict,
        decision: str,
        context: dict,
    ) -> dict:
        qm = get_quota_manager()
        if not qm.should_use_llm("future_self"):
            logger.info("[FutureSelfAgent] Quota mode '%s' — using fallback", qm.mode)
            return self._fallback(timeline_label, archetype)

        prompt = self.build_prompt(
            timeline_label=timeline_label,
            archetype=archetype,
            timeline_data=json.dumps(timeline_data, indent=2, default=str),
            decision=decision,
            context=json.dumps(context, indent=2, default=str),
        )

        try:
            result = self.run_structured(prompt)
            if "persona" not in result:
                raise ValueError("Missing 'persona' key")
            result["persona"]["timeline_label"] = timeline_label
            return result["persona"]
        except Exception as exc:
            logger.warning("[FutureSelfAgent] LLM failed for %s: %s", timeline_label, exc)
            return self._fallback(timeline_label, archetype)

    def create_all_personas(
        self,
        decision: str,
        context: dict,
        archetypes: Dict[str, str],
    ) -> Dict[str, dict]:
        """Generate all three personas in a single LLM call."""
        qm = get_quota_manager()
        if not qm.should_use_llm("future_self_batch"):
            logger.info("[FutureSelfAgent] Quota mode '%s' — using individual fallbacks", qm.mode)
            return {tl: self._fallback(tl, arch) for tl, arch in archetypes.items()}

        prompt = _BATCH_PROMPT_TEMPLATE.format(
            decision=decision,
            context=json.dumps(context, indent=2, default=str),
            age=context.get("age", 30),
        )

        try:
            raw = self.run(prompt)
            result = json.loads(raw)
            personas = {}
            for tl_key in archetypes:
                entry = result.get(tl_key, {})
                entry["timeline_label"] = tl_key
                personas[tl_key] = entry
            return personas
        except Exception as exc:
            logger.warning("[FutureSelfAgent] Batch LLM failed: %s — using individual fallbacks", exc)
            return {tl: self._fallback(tl, arch) for tl, arch in archetypes.items()}

    def _fallback(self, timeline_label: str, archetype: str) -> dict:
        voices = {
            "The Settler": {"voice": "reflective", "tone": "warm and grounded"},
            "The Climber": {"voice": "pragmatic", "tone": "measured and proud"},
            "The Gambler": {"voice": "intense", "tone": "honest and energized"},
        }
        v = voices.get(archetype, {"voice": "reflective", "tone": "thoughtful"})
        return {
            "timeline_label": timeline_label,
            "name": f"Future You ({archetype})",
            "age": 30,
            "occupation": "Technology Professional",
            "location": "Bangalore",
            "biography": f"Looking back on a decade defined by the {archetype.lower()} path. You made choices consistent with your values and are still discovering what those choices mean.",
            "personality_traits": ["Reflective", "Honest", "Self-aware"],
            "core_values": ["Growth", "Authenticity", "Connection"],
            "biggest_lesson": "The path you choose matters less than how consciously you walk it.",
            "biggest_regret": "Not asking myself sooner what I actually wanted, not what I was supposed to want.",
            "proudest_moment": "The night I realized I could trust myself to make hard decisions.",
            "current_challenges": ["Balancing the next chapter with the commitments of this one"],
            "advice_to_past_self": "Pay attention to what drains you versus what fills you. The data is there from Year 1.",
            "perspectives": {
                "on_risk": "Risk is not binary. The real risk is not knowing what you're optimizing for.",
                "on_career": "Career is a compounding asset. Invest in it, but know when to take profits.",
                "on_relationships": "Relationships are the only thing that appreciate predictably. Everything else fluctuates.",
                "on_health": "Health is the one asset you can't buy more of. You only realize this when it depreciates.",
                "on_money": "Money is freedom, but only up to the point where you have enough. After that it's just scorekeeping.",
                "on_the_path_not_taken": "Every path has a version of regret. Choose the one whose regrets you can live with.",
            },
            "voice_style": v["voice"],
        }


class FutureChatAgent(LLMAgent):
    def __init__(self):
        super().__init__("future_chat", "future_chat.txt", temperature=0.8)

    def chat(
        self,
        persona: dict,
        timeline_data: dict,
        question: str,
        conversation_history: Optional[list] = None,
    ) -> str:
        qm = get_quota_manager()
        history = conversation_history or []

        if not qm.should_use_llm("future_chat"):
            logger.info("[FutureChatAgent] Quota mode '%s' — using fallback", qm.mode)
            return self._fallback(persona, question)

        prompt = self.build_prompt(
            persona=json.dumps(persona, indent=2, default=str),
            timeline_data=json.dumps(timeline_data, indent=2, default=str),
            conversation_history=json.dumps(history, indent=2) if history else "No prior conversation.",
            user_question=question,
            voice_style=persona.get("voice_style", "reflective"),
        )

        try:
            raw = self.run(prompt, use_cache=False)
            return raw.strip()
        except Exception as exc:
            logger.warning("[FutureChatAgent] LLM failed: %s", exc)
            return self._fallback(persona, question)

    def _fallback(self, persona: dict, question: str) -> str:
        name = persona.get("name", "Your future self")
        lesson = persona.get("biggest_lesson", "every choice has a cost")
        return f"Looking back from where I am now, I'd say: {lesson}. Your question about '{question[:60]}...' is exactly the kind of thing I wish I'd asked myself more often back then. The answer isn't simple, but here's what I've learned — the quality of your decisions matters more than any single outcome."
