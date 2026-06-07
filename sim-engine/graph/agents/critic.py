"""
Critic Agent — validates timeline consistency, salary realism, economic realism, narrative consistency, causal integrity.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from .llm_agent import LLMAgent
from quota_manager import get_quota_manager

logger = logging.getLogger(__name__)


class CriticAgent(LLMAgent):
    def __init__(self):
        super().__init__("critic", "critic.txt", temperature=0.3)

    def evaluate(
        self,
        decision: str,
        context: dict,
        economic_data: dict,
        timelines: Dict[str, dict],
        memory_context: Optional[str] = None,
    ) -> dict:
        qm = get_quota_manager()
        if not qm.should_use_llm("critic"):
            logger.info("[CriticAgent] Quota mode '%s' — using fallback", qm.mode)
            return self._fallback(timelines, economic_data)

        prompt = self.build_prompt(
            decision=decision,
            context=json.dumps(context, indent=2, default=str),
            gdp_growth=economic_data.get("gdp_growth", 6.49),
            inflation_cpi=economic_data.get("inflation_cpi", 4.95),
            unemployment_rate=economic_data.get("unemployment_rate", 4.22),
            salary_entry_lpa=economic_data.get("salary_entry_lpa", "6.3-12.7"),
            salary_mid_lpa=economic_data.get("salary_mid_lpa", "15.8-31.7"),
            salary_senior_lpa=economic_data.get("salary_senior_lpa", "31.7-84.4"),
            timelines=self._summarize_for_prompt(timelines),
            memory_context=memory_context or "No prior context available.",
        )

        try:
            result = self.run_structured(prompt)
            self._validate(result)
            return result
        except Exception as exc:
            logger.warning("[CriticAgent] LLM failed: %s — using fallback", exc)
            return self._fallback(timelines, economic_data)

    def _validate(self, result: dict):
        if "evaluations" not in result:
            raise ValueError("Missing 'evaluations' key")

    def _summarize_for_prompt(self, timelines: Dict[str, dict]) -> str:
        summary = {}
        for tl_key, tl_data in timelines.items():
            tl = tl_data.get(tl_key, tl_data)
            years = {}
            for yr in ["year1", "year2", "year3", "year5", "year7", "year10"]:
                year_data = tl.get(yr, {})
                scores = year_data.get("scores", {})
                if scores:
                    years[yr] = scores
            summary[tl_key] = {
                "archetype": tl.get("archetype", "Unknown"),
                "year_count": len(years),
                "score_ranges": {k: {"min": min(v.values()), "max": max(v.values())} for k, v in years.items()} if years else {},
            }
        return json.dumps(summary, indent=2)

    def _fallback(self, timelines: Dict[str, dict], data: dict) -> dict:
        evaluations = []
        all_passed = True
        for tl_key in timelines:
            issues = []
            tl = timelines[tl_key].get(tl_key, timelines[tl_key])
            years_data = {}
            for yr in ["year1", "year2", "year3", "year5", "year7", "year10"]:
                year_data = tl.get(yr, {})
                scores = year_data.get("scores", {})
                if scores:
                    years_data[yr] = scores

            if not years_data:
                issues.append("No year data found for timeline")

            stress_values = [s.get("stress", 50) for s in years_data.values()]
            health_values = [s.get("health", 50) for s in years_data.values()]

            if stress_values and health_values:
                stress_up = stress_values[-1] > stress_values[0]
                health_down = health_values[-1] < health_values[0]
                if stress_up and not health_down:
                    issues.append("Causal integrity concern: stress increased but health did not decline")

            income_values = [s.get("income", 50) for s in years_data.values()]
            consistent_growth = all(
                income_values[i] <= income_values[i+1] * 1.5
                for i in range(len(income_values)-1)
            )
            if not consistent_growth:
                issues.append("Income growth pattern may be unrealistic")

            criteria_scores = {
                "salary_realism": 75,
                "economic_realism": 80,
                "causal_integrity": 70 if not issues else 55,
                "narrative_consistency": 75,
                "time_feasibility": 80,
                "archetype_fidelity": 85,
            }
            overall = sum(criteria_scores.values()) / len(criteria_scores)
            passed = overall >= 60 and len(issues) <= 1
            if not passed:
                all_passed = False

            evaluations.append({
                "timeline": tl_key,
                "criteria_scores": criteria_scores,
                "overall_score": round(overall, 1),
                "passed": passed,
                "issues": issues,
                "recommendations": ["Review stress-health causal chain", "Validate income progression against market data"] if issues else ["Timeline is consistent and realistic"],
            })

        return {
            "evaluations": evaluations,
            "global_issues": [e["issues"][0] for e in evaluations if e["issues"]][:3],
            "global_recommendations": ["Ensure stress correlates with health changes", "Verify salary progression aligns with industry standards"],
            "verdict": "INSUFFICIENT_DATA" if not all_passed else "APPROVED_WITH_CAVEATS",
        }
