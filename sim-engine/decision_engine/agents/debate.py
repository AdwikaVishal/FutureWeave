from __future__ import annotations
import math
import logging
from typing import Dict, List, Tuple
from . import BaseAgent
from ..types import AgentOutput, DebateResult, DebateEntry, SIMULATION_YEARS

logger = logging.getLogger(__name__)


class DebateEngine:
    def run(self, agent_outputs: Dict[str, AgentOutput]) -> DebateResult:
        entries = []
        voting_matrix: Dict[str, Dict[str, float]] = {}

        for name in agent_outputs:
            voting_matrix[name] = {}

        topics = [
            ("safe_vs_ambitious", "Safe path vs ambitious path", ["risk", "financial", "opportunity", "identity", "career"]),
            ("best_option", "Which decision option is best", list(agent_outputs.keys())),
            ("stability_vs_growth", "Stability vs growth priority", ["risk", "opportunity", "career", "financial", "strategic", "lifestyle"]),
            ("income_vs_purpose", "Income vs purpose trade-off", ["financial", "happiness", "identity", "lifestyle"]),
            ("short_vs_long_term", "Short-term vs long-term thinking", ["risk", "strategic", "time", "opportunity", "financial"]),
            ("speed_of_action", "Act now vs wait", ["time", "risk", "opportunity", "financial", "identity"]),
        ]

        for topic_id, topic_desc, agent_names in topics:
            relevant = {n: agent_outputs[n] for n in agent_names if n in agent_outputs}
            if len(relevant) < 2:
                continue

            positions = {n: ao.score for n, ao in relevant.items()}
            scores_list = list(positions.values())
            center = sum(scores_list) / len(scores_list)
            disagreement = math.sqrt(sum((s - center) ** 2 for s in scores_list) / len(scores_list))
            consensus = 100 - min(disagreement * 3, 80)

            tension_score = min(100, disagreement * 8)
            resolved = self._resolve_topic(topic_id, positions, center, agent_outputs)
            tension_pair = self._find_tension_pair(positions)

            entries.append(DebateEntry(
                topic=topic_desc,
                agents_involved=list(positions.keys()),
                positions={n: round(s, 1) for n, s in positions.items()},
                consensus_score=round(max(0, consensus), 1),
                disagreement_score=round(min(100, disagreement * 5), 1),
                tension_score=round(tension_score, 1),
                resolution=resolved,
                key_tension_pair=tension_pair,
                root_cause=self._find_root_cause(topic_id, positions, agent_outputs),
            ))

            for n in positions:
                for m in positions:
                    if n != m:
                        diff = abs(positions[n] - positions[m])
                        agreement = max(0, 100 - diff * 2)
                        voting_matrix.setdefault(n, {})[m] = round(agreement, 1)

        overall_tension = sum(e.tension_score for e in entries) / len(entries) if entries else 0
        consensus_summary = self._build_summary(entries, agent_outputs, overall_tension)
        primary_disagreement = max(entries, key=lambda e: e.disagreement_score).topic if entries else ""
        agent_alliances = self._find_alliances(voting_matrix)

        logger.info("[DebateEngine] %d topics debated, overall tension=%.1f, primary_disagreement=%s",
                    len(entries), overall_tension, primary_disagreement)

        return DebateResult(
            entries=entries,
            voting_matrix=voting_matrix,
            consensus_summary=consensus_summary,
            overall_tension_score=round(overall_tension, 1),
            primary_disagreement=primary_disagreement,
            agent_alliances=agent_alliances,
        )

    def _resolve_topic(self, topic_id: str, positions: Dict[str, float], center: float, agent_outputs: Dict[str, AgentOutput]) -> str:
        if topic_id == "safe_vs_ambitious":
            risk_score = positions.get("risk", 50)
            opp_score = positions.get("opportunity", 50)
            diff = opp_score - risk_score
            if diff > 15:
                return "Agents favor ambitious path — opportunity outweighs risk"
            elif diff < -15:
                return "Agents favor safe path — risk concerns dominate"
            else:
                return "Agents evenly split between safe and ambitious paths"
        elif topic_id == "best_option":
            per_option_consensus: Dict[str, List[float]] = {}
            for name, ao in agent_outputs.items():
                if hasattr(ao, "per_option_scores") and ao.per_option_scores:
                    for opt, sc in ao.per_option_scores.items():
                        per_option_consensus.setdefault(opt, []).append(sc)
            if per_option_consensus:
                avg_scores = {opt: sum(scs)/len(scs) for opt, scs in per_option_consensus.items()}
                best = max(avg_scores, key=avg_scores.get)
                return f"Consensus leans toward '{best}' as the optimal choice"
            return "No clear consensus on best option"
        elif topic_id == "stability_vs_growth":
            risk_scores = [positions.get(n, 50) for n in ["risk", "lifestyle"]]
            growth_scores = [positions.get(n, 50) for n in ["opportunity", "career", "strategic"]]
            if sum(growth_scores) / len(growth_scores) > sum(risk_scores) / len(risk_scores) + 15:
                return "Growth-oriented path recommended by most agents"
            elif sum(risk_scores) / len(risk_scores) > sum(growth_scores) / len(growth_scores) + 15:
                return "Stability-focused path recommended by most agents"
            else:
                return "Balanced growth-stability approach recommended"
        elif topic_id == "income_vs_purpose":
            income_pos = positions.get("financial", 50)
            purpose_pos = sum(positions.get(n, 50) for n in ["happiness", "identity", "lifestyle"]) / 3
            if income_pos > purpose_pos + 15:
                return "Income optimization slightly favored"
            elif purpose_pos > income_pos + 15:
                return "Purpose and fulfillment prioritized over income"
            else:
                return "Income and purpose in reasonable balance"
        elif topic_id == "short_vs_long_term":
            short_pos = sum(positions.get(n, 50) for n in ["financial", "risk"]) / 2
            long_pos = sum(positions.get(n, 50) for n in ["strategic", "time", "opportunity"]) / 3
            if long_pos > short_pos + 15:
                return "Long-term thinking dominates — agents favor patience"
            elif short_pos > long_pos + 15:
                return "Short-term considerations dominate — agents favor action"
            else:
                return "Balanced time horizon approach"
        elif topic_id == "speed_of_action":
            now = sum(positions.get(n, 50) for n in ["time", "opportunity", "identity"]) / 3
            wait = sum(positions.get(n, 50) for n in ["risk", "financial"]) / 2
            if now > wait + 15:
                return "Act now — timing windows are favorable"
            elif wait > now + 15:
                return "Wait for better conditions — patience reduces risk"
            else:
                return "No urgency either way — deliberate decision-making"
        return "Moderate consensus across agents"

    def _find_tension_pair(self, positions: Dict[str, float]) -> tuple:
        if len(positions) < 2:
            return ("", "")
        pairs = [(a, b) for a in positions for b in positions if a < b]
        if not pairs:
            return ("", "")
        return max(pairs, key=lambda p: abs(positions[p[0]] - positions[p[1]]))

    def _find_root_cause(self, topic_id: str, positions: Dict[str, float], agent_outputs: Dict[str, AgentOutput]) -> str:
        if len(positions) < 2:
            return "Insufficient agents to determine root cause"
        vals = list(positions.items())
        vals.sort(key=lambda x: x[1])
        low_agent, high_agent = vals[0], vals[-1]
        diff = high_agent[1] - low_agent[1]
        if diff > 30:
            return f"Fundamental disagreement between {low_agent[0]} (scores low) and {high_agent[0]} (scores high) — driven by different risk/reward evaluation"
        elif diff > 15:
            return f"Moderate tension between {low_agent[0]} and {high_agent[0]} — differing weight on uncertainty"
        else:
            return "Minor differences driven by modeling assumptions"

    def _build_summary(self, entries: List[DebateEntry], agent_outputs: Dict[str, AgentOutput], tension: float) -> str:
        if not entries:
            return "No debate topics generated"
        avg_consensus = sum(e.consensus_score for e in entries) / len(entries)
        high_disagreement = [e for e in entries if e.disagreement_score > 40]

        if avg_consensus > 70:
            base = "Strong consensus across most dimensions. "
        elif avg_consensus > 45:
            base = "Moderate agreement with some notable disagreements. "
        else:
            base = "Significant disagreement among agents. "

        if tension > 60:
            base += f"Decision tension is HIGH ({tension:.0f}/100) — agents are sharply divided. "
        elif tension > 35:
            base += f"Decision tension is moderate ({tension:.0f}/100). "

        if high_disagreement:
            topics = "; ".join(e.topic for e in high_disagreement[:3])
            base += f"Key disagreements on: {topics}. "

        overall_scores = [ao.score for ao in agent_outputs.values()]
        if overall_scores:
            mu = sum(overall_scores) / len(overall_scores)
            low = min(overall_scores)
            high = max(overall_scores)
            base += f"Agent scores range from {low:.0f} to {high:.0f} (mean {mu:.0f}). "

        return base.strip()

    def _find_alliances(self, voting_matrix: Dict[str, Dict[str, float]]) -> List[List[str]]:
        alliances = []
        agents = list(voting_matrix.keys())
        for i, a in enumerate(agents):
            for b in agents[i + 1:]:
                agreement = voting_matrix.get(a, {}).get(b, 0)
                if agreement > 80:
                    alliance = [a, b]
                    existing = False
                    for al in alliances:
                        if a in al or b in al:
                            al.extend([x for x in alliance if x not in al])
                            existing = True
                            break
                    if not existing:
                        alliances.append(alliance)
        return alliances
