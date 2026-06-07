"""
Timeline Agent — generates three life simulation timelines (A: Settler, B: Climber, C: Gambler).
"""
import json
import logging
from typing import Any, Dict, Optional

from .llm_agent import LLMAgent
from quota_manager import get_quota_manager

logger = logging.getLogger(__name__)

TIMELINE_PROMPTS = {
    "Timeline A": "timeline_a.txt",
    "Timeline B": "timeline_b.txt",
    "Timeline C": "timeline_c.txt",
}

ARCHETYPE_BIAS = {
    "Timeline A": {"income": -3, "stress": -12, "relationships": +12, "opportunity": -8, "career_growth": -5},
    "Timeline B": {"income": 0, "stress": +2, "relationships": 0, "opportunity": +5, "career_growth": +8},
    "Timeline C": {"income": +6, "stress": +18, "relationships": -10, "opportunity": +15, "career_growth": +6},
}


class TimelineAgent(LLMAgent):
    def __init__(self, timeline_key: str):
        prompt_file = TIMELINE_PROMPTS.get(timeline_key, "timeline_b.txt")
        super().__init__(f"timeline_{timeline_key[-1].lower()}", prompt_file, temperature=0.7)
        self.timeline_key = timeline_key
        self.archetype = {"Timeline A": "The Settler", "Timeline B": "The Climber", "Timeline C": "The Gambler"}.get(timeline_key, "The Climber")

    def generate(
        self,
        decision: str,
        context: dict,
        economic_output: dict,
        career_output: dict,
        financial_output: dict,
        health_output: dict,
        relationship_output: dict,
        opportunity_output: dict,
        debate_resolution: dict,
        events: list,
        memory_context: Optional[str] = None,
    ) -> dict:
        qm = get_quota_manager()
        if not qm.should_use_llm(f"timeline_{self.timeline_key[-1].lower()}"):
            logger.info("[TimelineAgent] Quota mode '%s' — using fallback for %s", qm.mode, self.timeline_key)
            return self._fallback(context, economic_output)

        prompt = self.build_prompt(
            decision=decision,
            context=json.dumps(context, indent=2, default=str),
            economic_output=self.format_dict(economic_output),
            career_output=self.format_dict(career_output),
            financial_output=self.format_dict(financial_output),
            health_output=self.format_dict(health_output),
            relationship_output=self.format_dict(relationship_output),
            opportunity_output=self.format_dict(opportunity_output),
            debate_resolution=self.format_dict(debate_resolution),
            events=json.dumps(events, indent=2) if events else "No significant events.",
            memory_context=memory_context or "No prior context available.",
        )

        try:
            raw = self.run(prompt)
            parsed = json.loads(raw)
            if self.timeline_key not in parsed:
                parsed = {self.timeline_key: parsed}
            self._validate(parsed)
            return parsed
        except Exception as exc:
            logger.warning("[TimelineAgent] LLM failed for %s: %s", self.timeline_key, exc)
            return self._fallback(context, economic_output)

    def _validate(self, result: dict):
        tl = result.get(self.timeline_key, {})
        for year in ["year1", "year2", "year3", "year5", "year7", "year10"]:
            if year not in tl:
                raise ValueError(f"Missing year {year} in {self.timeline_key}")

    def _fallback(self, context: dict, eco: dict) -> dict:
        bias = ARCHETYPE_BIAS.get(self.timeline_key, {})
        income_base = 30 + bias.get("income", 0)
        stress_base = 55 + bias.get("stress", 0)
        rel_base = 60 + bias.get("relationships", 0)
        opp_base = 65 + bias.get("opportunity", 0)
        cg_base = 50 + bias.get("career_growth", 0)
        health_base = 65 - (stress_base - 55) * 0.3

        archetype_narratives = {
            "The Settler": {
                "year1": "You begin by laying a stable foundation — prioritizing consistency over speed, building routines that protect your wellbeing.",
                "year2": "The slow-and-steady approach starts to compound. Colleagues respect your reliability. You deepen a few key relationships.",
                "year3": "A significant personal or professional milestone arrives. Your early caution now looks like wisdom as others burn out around you.",
                "year5": "Five years in, the stability you built unlocks opportunities that require a grounded base. Your network is deep, not wide.",
                "year7": "The Settler path proves its worth during turbulent times. While others scramble, you have reserves — emotional, financial, relational.",
                "year10": "A decade of consistency delivers what flash-in-the-pan approaches never could: sustainable success, deep trust, and genuine contentment.",
            },
            "The Climber": {
                "year1": "You hit the ground running, taking on stretch assignments and building visibility. Early results validate your ambitious approach.",
                "year2": "The first major promotion comes faster than peers. You're learning that growth requires sacrifice, but the trajectory feels worth it.",
                "year3": "You hit a career groove — responsibilities grow, income jumps. But you notice the first signs of strain in relationships and health.",
                "year5": "By year five, you've outperformed most of your cohort. The question shifting from 'how high?' to 'at what cost?' becomes harder to ignore.",
                "year7": "A plateau or recalibration. The climb continues but you're more strategic about what you scale. Work-life boundaries get renegotiated.",
                "year10": "You've reached a position of influence. The view from the top is clarifying — you see both what you gained and what you traded to get here.",
            },
            "The Gambler": {
                "year1": "You take a bet that others thought was risky. The initial volatility tests your conviction but also opens doors the cautious never see.",
                "year2": "A big swing pays off — or doesn't. Either way, you learn more in one year than most do in five. Your tolerance for uncertainty grows.",
                "year3": "The gambler's path is a series of asymmetric bets. Some fail spectacularly, but the winners more than compensate. Your network polarizes.",
                "year5": "By year five, the path has been anything but linear. You've had highs that validated the approach and lows that tested your resolve.",
                "year7": "You've developed a nose for opportunity that slower paths never train. The volatility smooths out as your judgment sharpens.",
                "year10": "Looking back, the gambler path was never really about the bets — it was about becoming someone who could handle any outcome.",
            },
        }
        narratives = archetype_narratives.get(self.archetype, {})

        years_def = [
            ("year1", 0, income_base, stress_base, health_base, rel_base, cg_base, opp_base),
            ("year2", 1, income_base + 5, stress_base + 3, health_base - 2, rel_base + 2, cg_base + 8, opp_base + 3),
            ("year3", 2, income_base + 12, stress_base + 5, health_base - 3, rel_base + 3, cg_base + 15, opp_base + 5),
            ("year5", 4, income_base + 22, stress_base + 8, health_base - 5, rel_base + 5, cg_base + 22, opp_base + 8),
            ("year7", 6, income_base + 35, stress_base + 10, health_base - 8, rel_base + 6, cg_base + 28, opp_base + 10),
            ("year10", 9, income_base + 50, stress_base + 8, health_base - 6, rel_base + 8, cg_base + 32, opp_base + 8),
        ]

        years = {}
        for yr_name, yr_idx, inc, stress, health, rel, cg, opp in years_def:
            narrative = narratives.get(yr_name, f"In {yr_name.replace('year', 'Year ')}, you continue on the {self.archetype} path.")
            years[yr_name] = {
                "narrative": narrative,
                "scores": {
                    "income": min(100, inc),
                    "career_growth": min(100, cg),
                    "stress": max(0, min(100, stress)),
                    "health": max(0, min(100, health)),
                    "relationships": max(0, min(100, rel)),
                    "happiness": max(0, min(100, round((inc + cg + rel - stress + health) / 5 + 50))),
                    "opportunity": min(100, opp),
                },
            }

        final_summaries = {
            "The Settler": "The Settler path delivered what it promised: a life built on sustainable choices, deep relationships, and quiet accomplishment. Not every year was exciting, but every year counted.",
            "The Climber": "The Climber path was a ride of ambition and tradeoffs. You reached heights that required sacrifice, but the person you became along the way was forged by both the wins and the costs.",
            "The Gambler": "The Gambler path was never going to be predictable — and it delivered on that promise. The decade was a series of peaks and valleys that ultimately shaped a resilient, sharp, adaptable version of you.",
        }
        final_outcome_narrative = final_summaries.get(self.archetype, f"The {self.archetype} path delivered a decade of growth and transformation.")

        return {
            self.timeline_key: {
                "archetype": self.archetype,
                **years,
                "final_outcome": {
                    "summary": final_outcome_narrative,
                    "satisfaction_score": max(30, min(90, 65 + bias.get("income", 0))),
                },
            }
        }


class TimelineAgentFactory:
    @staticmethod
    def create_all() -> Dict[str, TimelineAgent]:
        return {k: TimelineAgent(k) for k in TIMELINE_PROMPTS}

    @staticmethod
    def batch_generate(
        decision: str,
        context: dict,
        economic_output: dict,
        career_output: dict,
        financial_output: dict,
        health_output: dict,
        relationship_output: dict,
        opportunity_output: dict,
        debate_resolution: dict,
        events: dict,
        memory_context: Optional[str] = None,
    ) -> Dict[str, dict]:
        from quota_manager import get_quota_manager
        qm = get_quota_manager()
        if not qm.should_use_llm("timeline_batch"):
            logger.info("[TimelineAgentFactory] Quota mode '%s' — using individual fallbacks", qm.mode)
            agents = TimelineAgentFactory.create_all()
            results = {}
            for tl_key, agent in agents.items():
                tl_events = events.get(tl_key, [])
                results[tl_key] = agent._fallback(context, economic_output)
            return results

        prompt = (
            f"Generate 3 alternate future timelines for someone facing this decision:\n\n"
            f"DECISION: {decision}\n"
            f"CONTEXT: {json.dumps(context, indent=2, default=str)}\n\n"
            f"ECONOMIC: {TimelineAgent.format_dict(economic_output)}\n"
            f"CAREER: {TimelineAgent.format_dict(career_output)}\n"
            f"FINANCIAL: {TimelineAgent.format_dict(financial_output)}\n"
            f"HEALTH: {TimelineAgent.format_dict(health_output)}\n"
            f"RELATIONSHIPS: {TimelineAgent.format_dict(relationship_output)}\n"
            f"OPPORTUNITY: {TimelineAgent.format_dict(opportunity_output)}\n"
            f"DEBATE: {TimelineAgent.format_dict(debate_resolution)}\n\n"
            f"Return a JSON object with keys \"Timeline A\", \"Timeline B\", \"Timeline C\".\n\n"
            f"Each timeline contains:\n"
            f"- archetype: \"The Settler\" | \"The Climber\" | \"The Gambler\"\n"
            f"- year1, year2, year3, year5, year7, year10: each with 'narrative' (2-3 sentences) and 'scores' dict (income, career_growth, stress, health, relationships, happiness, opportunity, 0-100)\n"
            f"- final_outcome: dict with 'summary' (2-3 sentences) and 'satisfaction_score' (0-100)\n\n"
            f"Timeline A — The Settler: Stable, cautious, prioritizes work-life balance and relationships.\n"
            f"Timeline B — The Climber: Ambitious, career-focused, willing to accept tradeoffs for advancement.\n"
            f"Timeline C — The Gambler: High-risk, high-reward, entrepreneurial, accepts volatility.\n\n"
            f"Make each timeline feel distinct and self-consistent."
        )

        agent = TimelineAgent("Timeline B")
        try:
            raw = agent.run(prompt)
            result = json.loads(raw)
            validated = {}
            for tl_key in ["Timeline A", "Timeline B", "Timeline C"]:
                tl = result.get(tl_key, {})
                if tl:
                    for year in ["year1", "year2", "year3", "year5", "year7", "year10"]:
                        if year not in tl:
                            tl[year] = {"narrative": "", "scores": {}}
                    validated[tl_key] = {tl_key: tl}
            if len(validated) == 3:
                logger.info("[TimelineAgentFactory] Batch LLM generated all 3 timelines in one call")
                return validated
        except Exception as exc:
            logger.warning("[TimelineAgentFactory] Batch LLM failed: %s — using individual fallbacks", exc)

        agents = TimelineAgentFactory.create_all()
        results = {}
        for tl_key, agent in agents.items():
            results[tl_key] = agent._fallback(context, economic_output)
        return results
