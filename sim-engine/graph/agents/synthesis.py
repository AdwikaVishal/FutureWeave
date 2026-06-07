"""
Synthesis Agent — combines all agent outputs into final recommendation, tradeoffs, hinge moments, regret analysis.
"""
import json
import logging
from typing import Any, Dict, Optional

from .llm_agent import LLMAgent
from quota_manager import get_quota_manager

logger = logging.getLogger(__name__)


class SynthesisAgent(LLMAgent):
    def __init__(self):
        super().__init__("synthesis", "synthesis.txt", temperature=0.65)

    def synthesize(
        self,
        decision: str,
        context: dict,
        agent_outputs: Dict[str, dict],
        debate_resolution: dict,
        timelines: Dict[str, dict],
        critic_evaluations: dict,
        future_self_personas: Dict[str, dict],
        monte_carlo_results: Optional[dict] = None,
    ) -> dict:
        qm = get_quota_manager()
        if not qm.should_use_llm("synthesis"):
            logger.info("[SynthesisAgent] Quota mode '%s' — using fallback", qm.mode)
            return self._fallback(decision, agent_outputs, timelines, monte_carlo_results)

        prompt = self.build_prompt(
            decision=decision,
            context=json.dumps(context, indent=2, default=str),
            economic_output=self.format_dict(agent_outputs.get("economic", {})),
            career_output=self.format_dict(agent_outputs.get("career", {})),
            financial_output=self.format_dict(agent_outputs.get("financial", {})),
            health_output=self.format_dict(agent_outputs.get("health", {})),
            relationship_output=self.format_dict(agent_outputs.get("relationship", {})),
            opportunity_output=self.format_dict(agent_outputs.get("opportunity", {})),
            debate_resolution=self.format_dict(debate_resolution),
            timelines=self._summarize_timelines(timelines),
            critic_evaluations=self.format_dict(critic_evaluations),
            future_selves=self.format_dict(future_self_personas),
            monte_carlo=self.format_dict(monte_carlo_results or {}),
        )

        try:
            result = self.run_structured(prompt)
            self._validate(result)
            return result
        except Exception as exc:
            logger.warning("[SynthesisAgent] LLM failed: %s — using fallback", exc)
            return self._fallback(decision, agent_outputs, timelines)

    def _validate(self, result: dict):
        for key in ["comparison", "hinge_point", "recommendation", "regret_analysis"]:
            if key not in result:
                raise ValueError(f"Missing key: {key}")

    def _summarize_timelines(self, timelines: Dict[str, dict]) -> str:
        summary = {}
        for tl_key, tl_data in timelines.items():
            tl = tl_data.get(tl_key, tl_data)
            years = {}
            for yr in ["year1", "year10"]:
                year_data = tl.get(yr, {})
                years[yr] = {
                    "narrative_preview": (year_data.get("narrative", "")[:120] + "...") if year_data.get("narrative") else "",
                    "scores": year_data.get("scores", {}),
                }
            summary[tl_key] = {
                "archetype": tl.get("archetype", "Unknown"),
                "final_outcome": tl.get("final_outcome", {}),
                "years_summary": years,
            }
        return json.dumps(summary, indent=2)

    def _fallback(self, decision: str, outputs: dict, timelines: dict, monte_carlo: Optional[dict] = None) -> dict:
        comparison = {}
        for tl_key, tl_data in timelines.items():
            tl = tl_data.get(tl_key, tl_data)
            y10 = tl.get("year10", {}).get("scores", {})
            mc_tl = {}
            if monte_carlo:
                tl_comp = monte_carlo.get("timeline_comparison", {}).get(tl_key, {})
                for node, stats in tl_comp.items():
                    if isinstance(stats, dict) and "mean" in stats:
                        mc_tl[node] = stats["mean"]
            comparison[tl_key] = {
                "archetype": tl.get("archetype", "Unknown"),
                "year10_state": tl.get("year10", {}).get("narrative", "")[:100],
                "happiness_score": mc_tl.get("happiness", y10.get("happiness", 50)),
                "health_score": mc_tl.get("health", y10.get("health", 50)),
                "key_tradeoff": "Stability vs. ambition" if tl.get("archetype") == "The Settler" else "Growth vs. wellbeing" if tl.get("archetype") == "The Climber" else "Upside vs. stability",
            }

        # Compute best path from Monte Carlo expected value if available
        if monte_carlo:
            mc = monte_carlo
            mc_success = mc.get("success_probability", 0)
            mc_failure = mc.get("failure_probability", 0)
            mc_neutral = mc.get("neutral_probability", 0)
            tl_scores = {}
            tl_comp = mc.get("timeline_comparison", {})
            for tl_key in timelines:
                scores = tl_comp.get(tl_key, {})
                happiness_mean = 50
                income_mean = 50
                if isinstance(scores, dict):
                    happiness_mean = scores.get("happiness", {}).get("mean", 50) if isinstance(scores.get("happiness"), dict) else 50
                    income_mean = scores.get("income", {}).get("mean", 50) if isinstance(scores.get("income"), dict) else 50
                tl_scores[tl_key] = happiness_mean * 0.6 + income_mean * 0.4
            best_tl = max(tl_scores, key=tl_scores.get)
            best_score = tl_scores[best_tl]
            mc_note = f"Monte Carlo shows {mc_success*100:.0f}% success, {mc_failure*100:.0f}% failure across {mc.get('iterations_run', 0)} simulations."
        else:
            best_tl = "Timeline B"
            best_score = 65
            mc_note = ""

        archetype_map = {"Timeline A": "The Settler", "Timeline B": "The Climber", "Timeline C": "The Gambler"}
        best_arch = archetype_map.get(best_tl, "The Climber")

        # Weighted total score for each timeline (item 14)
        tl_weighted_scores = {}
        for tl_key, tl_data in timelines.items():
            tl = tl_data.get(tl_key, tl_data)
            y10 = tl.get("year10", {}).get("scores", {})
            mc_tl = {}
            if monte_carlo:
                tl_comp_inner = monte_carlo.get("timeline_comparison", {}).get(tl_key, {})
                for node, stats in tl_comp_inner.items():
                    if isinstance(stats, dict) and "mean" in stats:
                        mc_tl[node] = stats["mean"]
            h = mc_tl.get("happiness", y10.get("happiness", 50))
            inc = mc_tl.get("income", y10.get("income", 50))
            he = mc_tl.get("health", y10.get("health", 50))
            rel = mc_tl.get("relationships", y10.get("relationships", 50))
            opp = mc_tl.get("opportunity", y10.get("opportunity", 50))
            risk_inv = 100 - mc_tl.get("risk", y10.get("risk", 25))
            total = (
                h * 0.25 + inc * 0.20 + he * 0.15 +
                rel * 0.15 + opp * 0.15 + risk_inv * 0.10
            )
            tl_weighted_scores[tl_key] = round(total, 1)

        weighted_best = max(tl_weighted_scores, key=tl_weighted_scores.get)
        weighted_best_score = tl_weighted_scores[weighted_best]
        best_arch_weighted = archetype_map.get(weighted_best, "The Climber")

        # Why Not panel (item 15) — explain why each alternative wasn't chosen
        why_not = {}
        for tl_key in timelines:
            if tl_key == weighted_best:
                continue
            alt_score = tl_weighted_scores.get(tl_key, 0)
            alt_arch = archetype_map.get(tl_key, "The Alternative")
            gap = round(weighted_best_score - alt_score, 1)
            why_not[tl_key] = {
                "alternative": f"{tl_key} ({alt_arch})",
                "not_recommended_because": (
                    f"Lower weighted total score ({alt_score}) vs {weighted_best} ({weighted_best_score}) — "
                    f"a gap of {gap} points. The {alt_arch.lower()} path offers "
                    f"{'higher upside but with more volatility' if 'Gambler' in alt_arch else 'more stability but less growth potential' if 'Settler' in alt_arch else 'faster growth but higher health tradeoffs'}."
                ),
                "what_would_need_to_change": (
                    "Stronger risk tolerance and support network" if "Gambler" in alt_arch
                    else "Higher income ambitions and growth focus" if "Settler" in alt_arch
                    else "Better health management and work-life boundaries"
                ),
                "score_gap": gap,
            }

        return {
            "comparison": comparison,
            "hinge_point": {
                "year": "Year3",
                "reason": "The decisions made between Year 1 and Year 3 compound into trajectories that are difficult to reverse by Year 5.",
                "what_to_watch_for": "Stress levels exceeding 45 or health dropping below 55 are warning signs.",
                "reversible": False,
            },
            "key_tradeoffs": [
                {"tradeoff": "Income growth vs. health and relationships", "severity": "high", "timeline": "Timeline C"},
                {"tradeoff": "Career acceleration vs. work-life balance", "severity": "medium", "timeline": "Timeline B"},
            ],
            "regret_analysis": {
                tl_key: {
                    "lost_opportunity": "The high-growth path not taken",
                    "missed_identity": "A version of yourself that prioritized differently",
                    "emotional_cost": "The quiet wondering about what could have been",
                }
                for tl_key in timelines
            },
            "recommendation": {
                "primary_path": weighted_best,
                "weighted_scores": tl_weighted_scores,
                "reasoning": f"{weighted_best} ({best_arch_weighted}) offers the best projected outcome (weighted total score: {weighted_best_score}/100). {mc_note}. Weighted formula: happiness×0.25 + income×0.20 + health×0.15 + relationships×0.15 + opportunity×0.15 + risk_inverse×0.10.".strip(),
                "guardrails": ["Cap weekly hours at 50", "Invest 10+ hours/week in relationships", "Build emergency fund before pursuing risky moves"],
                "reassessment_triggers": ["If stress exceeds 55 for 6+ months", "If health score drops below 50", "If relationship satisfaction drops below 45"],
            },
            "why_not": why_not,
            "future_letter": {
                tl_key: self._generate_letter(tl_key, tl) for tl_key, tl in timelines.items()
            },
        }

    def _generate_letter(self, tl_key: str, tl_data: dict) -> str:
        archetype = tl_data.get(tl_key, tl_data).get("archetype", "Your future self")
        y10 = tl_data.get(tl_key, tl_data).get("year10", {})
        narrative = y10.get("narrative", "You made it through the decade.")
        return f"Dear younger me,\n\n{narrative}\n\nLooking back, I realize the {archetype.lower()} path gave me exactly what I optimized for. The question is whether I optimized for the right things. You'll have to answer that for yourself when you get here.\n\nWith hard-won wisdom,\nYou (10 years later)"
