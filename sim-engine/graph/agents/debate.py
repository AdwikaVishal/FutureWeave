"""
Debate Agent — resolves conflicts between agent outputs, identifies tradeoffs.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from .llm_agent import LLMAgent
from quota_manager import get_quota_manager

logger = logging.getLogger(__name__)


class DebateAgent(LLMAgent):
    def __init__(self):
        super().__init__("debate", "debate.txt", temperature=0.6)

    def resolve(
        self,
        decision: str,
        agent_outputs: Dict[str, dict],
    ) -> dict:
        qm = get_quota_manager()
        conflicts = self._detect_conflicts(agent_outputs)

        if not conflicts:
            return {
                "debates": [],
                "consensus_points": ["All agents are in agreement — no significant conflicts detected."],
                "critical_tradeoffs": [],
                "balanced_recommendation": "No conflicts to resolve. All analyses are consistent.",
                "overall_confidence": 0.95,
            }

        if not qm.should_use_llm("debate"):
            logger.info("[DebateAgent] Quota mode '%s' — using fallback", qm.mode)
            return self._fallback(conflicts, agent_outputs)

        prompt = self.build_prompt(
            decision=decision,
            economic_output=self.format_dict(agent_outputs.get("economic", {})),
            career_output=self.format_dict(agent_outputs.get("career", {})),
            financial_output=self.format_dict(agent_outputs.get("financial", {})),
            health_output=self.format_dict(agent_outputs.get("health", {})),
            relationship_output=self.format_dict(agent_outputs.get("relationship", {})),
            opportunity_output=self.format_dict(agent_outputs.get("opportunity", {})),
            conflicts=json.dumps(conflicts, indent=2),
        )

        try:
            result = self.run_structured(prompt)
            self._validate(result)
            return result
        except Exception as exc:
            logger.warning("[DebateAgent] LLM failed: %s — using fallback", exc)
            return self._fallback(conflicts, agent_outputs)

    def _validate(self, result: dict):
        for key in ["debates", "consensus_points", "critical_tradeoffs", "balanced_recommendation"]:
            if key not in result:
                raise ValueError(f"Missing key: {key}")

    def _detect_conflicts(self, outputs: Dict[str, dict]) -> List[dict]:
        conflicts = []
        scores: Dict[str, Dict[str, float]] = {}

        for agent_name, data in outputs.items():
            if isinstance(data, dict):
                scores[agent_name] = self._extract_scores(data)

        agent_pairs = [
            ("economic", "financial"),
            ("career", "health"),
            ("career", "relationship"),
            ("financial", "health"),
            ("opportunity", "health"),
            ("opportunity", "relationship"),
        ]

        for a, b in agent_pairs:
            if a in scores and b in scores:
                for metric in ["income", "stress", "happiness"]:
                    va = scores[a].get(metric, 50)
                    vb = scores[b].get(metric, 50)
                    if abs(va - vb) > 15:
                        conflicts.append({
                            "topic": f"{metric} projection mismatch between {a} and {b}",
                            "agent_a": a,
                            "agent_b": b,
                            "value_a": va,
                            "value_b": vb,
                            "gap": abs(va - vb),
                            "description": f"{a} projects {metric}={va}, {b} projects {metric}={vb}",
                        })

        return conflicts

    def _extract_scores(self, data: dict) -> Dict[str, float]:
        scores = {}
        for key in data:
            if isinstance(data[key], (int, float)):
                scores[key] = float(data[key])
            elif isinstance(data[key], list) and len(data[key]) > 0:
                if isinstance(data[key][0], dict) and "score" in data[key][0]:
                    vals = [item.get("score", 0) for item in data[key] if isinstance(item, dict)]
                    if vals:
                        scores[key] = sum(vals) / len(vals)
        return scores

    def _fallback(self, conflicts: List[dict], outputs: dict) -> dict:
        debates = []
        for c in conflicts[:3]:
            debates.append({
                "topic": c["topic"],
                "agent_a": c["agent_a"],
                "agent_b": c["agent_b"],
                "position_a": f"Projects {c.get('agent_a', 'unknown')} value at {c.get('value_a', '?')}",
                "position_b": f"Projects {c.get('agent_b', 'unknown')} value at {c.get('value_b', '?')}",
                "resolution": f"The actual outcome likely lies between {c.get('value_a', '?')} and {c.get('value_b', '?')}, depending on timeline choices and external factors.",
                "tradeoff_identified": "Different time horizons and risk assumptions drive the divergence.",
                "weight": round(c.get("gap", 10) / 100, 2),
            })

        return {
            "debates": debates,
            "consensus_points": ["All agents agree this decision has significant career and financial implications.", "Health and relationship costs are the primary tradeoff for career acceleration."],
            "critical_tradeoffs": [
                {"tradeoff": "Career growth vs. Health/Relationships", "severity": "high", "recommendation": "Hard-cap weekly hours at 50 to preserve health and relationship capacity."},
                {"tradeoff": "Income vs. Stress", "severity": "medium", "recommendation": "Build financial buffer to reduce stress even during high-income periods."},
            ],
            "balanced_recommendation": "The optimal path balances career ambition with explicit guardrails on health and relationships. Target high career growth but enforce 50-hour work weeks and 10+ hours/week of relationship investment.",
            "overall_confidence": 0.72,
        }
