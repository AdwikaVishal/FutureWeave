from __future__ import annotations
import uuid
import json
import logging
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .types import (
    SimulationResult, UserProfile, EconomicData, AgentOutput,
    DebateResult, MonteCarloResult, ConfidenceBreakdown,
    DecisionOption, FuturePath, SIMULATION_YEARS,
)
from .decision_parser import parse_decision
from .profile_builder import build_user_profile
from .timeline_engine import generate_future_paths
from .monte_carlo_engine import run_monte_carlo
from .confidence_engine import compute_confidence
from .causal_graph import build_causal_graph
from .pivot_engine import compute_pivot
from .real_data_engine import compute_real_data_scores
from .regret_engine import compute_regret
from .life_dashboard_engine import compute_life_dashboard
from data_grounding import get_grounding_data, normalise_location
from .agents.financial import FinancialAgent
from .agents.risk_agent import RiskAgent
from .agents.opportunity import OpportunityAgent
from .agents.health import HealthAgent
from .agents.relationship import RelationshipAgent
from .agents.time_agent import TimeAgent
from .agents.happiness import HappinessAgent
from .agents.identity import IdentityAgent
from .agents.career import CareerAgent
from .agents.strategic import StrategicAgent
from .agents.lifestyle import LifestyleAgent
from .agents.economic import EconomicAgent
from .agents.debate import DebateEngine

logger = logging.getLogger(__name__)

AGENT_NAMES = [
    "financial", "risk", "opportunity", "health", "relationship",
    "time", "happiness", "identity", "career", "strategic",
    "lifestyle", "economic",
]


class DecisionPipeline:
    def __init__(self):
        self.agents = {
            "financial": FinancialAgent(),
            "risk": RiskAgent(),
            "opportunity": OpportunityAgent(),
            "health": HealthAgent(),
            "relationship": RelationshipAgent(),
            "time": TimeAgent(),
            "happiness": HappinessAgent(),
            "identity": IdentityAgent(),
            "career": CareerAgent(),
            "strategic": StrategicAgent(),
            "lifestyle": LifestyleAgent(),
            "economic": EconomicAgent(),
        }
        self.debate_engine = DebateEngine()

    def run(
        self,
        decision: str,
        context: Dict[str, Any],
        economic_override: Optional[Dict[str, Any]] = None,
        enable_monte_carlo: bool = True,
        monte_carlo_iterations: int = 10000,
    ) -> SimulationResult:
        logger.info("=" * 70)
        logger.info("[Pipeline] DIP Simulation: decision=%s", decision)
        logger.info("[Pipeline] Context: %s", json.dumps(context, default=str)[:500])

        parsed = parse_decision(decision)
        profile = self._build_profile(context)
        enriched = {**context, "_decision": decision}
        economic = self._build_economic_data(enriched, economic_override)
        grounding = self._extract_grounding(enriched)

        real_data = compute_real_data_scores(economic, profile, grounding)
        economic.economic_score = real_data.economic_score
        economic.employment_score = real_data.employment_score
        economic.industry_score = real_data.industry_score
        economic.cost_of_living_score = real_data.cost_of_living_score
        economic.salary_score = real_data.salary_score
        economic.data_freshness = real_data.data_freshness
        economic.data_completeness = real_data.data_completeness

        logger.info("[Pipeline] Real Data Scores: econ=%.1f employ=%.1f industry=%.1f col=%.1f salary=%.1f",
                    real_data.economic_score, real_data.employment_score, real_data.industry_score,
                    real_data.cost_of_living_score, real_data.salary_score)

        options = self._generate_options(decision, parsed, profile, economic)
        future_paths = generate_future_paths(profile, economic, options)

        agent_outputs = self._run_agents(decision, profile, economic, future_paths, options)
        debate_result = self.debate_engine.run(agent_outputs)

        monte_carlo = None
        if enable_monte_carlo:
            monte_carlo = run_monte_carlo(profile, economic, iterations=monte_carlo_iterations)

        regret_analysis = compute_regret(decision, profile, economic, future_paths, agent_outputs, options)
        life_dashboard = compute_life_dashboard(future_paths, agent_outputs, profile, economic, options)

        missing = self._get_missing_data(economic)
        confidence = compute_confidence(agent_outputs, monte_carlo or MonteCarloResult(), economic, missing)

        causal_graph = None
        try:
            causal_future = list(future_paths.values())[0] if future_paths else FuturePath()
            causal_graph = build_causal_graph({"Default": _future_to_timeline_like(causal_future)})
        except Exception:
            pass

        warnings = self._generate_warnings(parsed, economic, confidence, real_data)

        economic_indicators = {
            "gdp_growth": economic.gdp_growth, "inflation_cpi": economic.inflation_cpi,
            "unemployment_rate": economic.unemployment_rate, "salary_growth_pct": economic.salary_growth_pct,
            "cost_of_living_index": economic.cost_of_living_index, "industry_health": economic.industry_health,
            "interest_rate": economic.interest_rate,
        }

        logger.info("[Pipeline] Simulation complete. Confidence: %.1f%% (%s)", confidence.overall, confidence.tier)
        logger.info("[Pipeline] Agent scores: %s", {k: v.score for k, v in agent_outputs.items()})
        logger.info("[Pipeline] Life Dashboard: %.1f | Regret Risk: %.1f%%",
                    life_dashboard.overall_score, regret_analysis.overall_regret_risk)
        logger.info("=" * 70)

        return SimulationResult(
            decision=decision,
            decision_parsing=parsed,
            user_profile=profile,
            economic_data=economic,
            options=options,
            future_paths=future_paths,
            agent_outputs=agent_outputs,
            debate_result=debate_result,
            monte_carlo=monte_carlo,
            confidence=confidence,
            regret_analysis=regret_analysis,
            life_dashboard=life_dashboard,
            causal_graph=causal_graph,
            simulation_id=str(uuid.uuid4())[:8],
            warnings=warnings,
            real_data_scores={
                "economic_score": real_data.economic_score,
                "employment_score": real_data.employment_score,
                "industry_score": real_data.industry_score,
                "cost_of_living_score": real_data.cost_of_living_score,
                "salary_score": real_data.salary_score,
                "confidence": real_data.confidence,
                "data_completeness": real_data.data_completeness,
                "breakdown": real_data.breakdown,
            },
            data_sources_used=real_data.data_sources_used,
            data_freshness=real_data.data_freshness,
            economic_indicators=economic_indicators,
        )

    def _build_profile(self, context: Dict[str, Any]) -> UserProfile:
        return build_user_profile(context)

    def _generate_options(self, decision: str, parsed: dict, profile: UserProfile, economic: EconomicData) -> List[DecisionOption]:
        decision_lower = decision.lower()
        keywords = {
            "quit": "Stay in Corporate", "startup": "Join Startup", "company": "Start Company",
            "found": "Start Company", "mba": "Pursue MBA", "abroad": "Move Abroad",
            "move": "Move Abroad", "relocate": "Move Abroad",
            "switch": "Switch Careers", "career": "Switch Careers",
            "remote": "Work Remotely", "gap": "Take Gap Year",
            "year": "Take Gap Year", "house": "Buy House",
        }
        options = []
        seen = set()
        for kw, opt_title in keywords.items():
            if kw in decision_lower and opt_title not in seen:
                seen.add(opt_title)
                options.append(DecisionOption(
                    title=opt_title,
                    risk_level="high" if opt_title in ("Start Company", "Join Startup", "Take Gap Year") else "moderate",
                    time_horizon="long" if opt_title in ("Buy House", "Start Company") else "medium",
                    upside_potential="high" if opt_title in ("Start Company", "Move Abroad") else "moderate",
                    downside_risk="high" if opt_title in ("Start Company", "Join Startup") else "moderate",
                ))

        if not options:
            options = [
                DecisionOption(title="Stay in Corporate", risk_level="low", time_horizon="long", upside_potential="low", downside_risk="low"),
                DecisionOption(title="Join Startup", risk_level="high", time_horizon="medium", upside_potential="high", downside_risk="high"),
                DecisionOption(title="Start Company", risk_level="high", time_horizon="long", upside_potential="very_high", downside_risk="very_high"),
            ]

        for opt in options:
            opt.description = f"Decision path: {opt.title}"
        logger.info("[Pipeline] Generated %d options: %s", len(options), [o.title for o in options])
        return options

    def _extract_grounding(self, context: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = context.get("_economic_snapshot", {})
        if isinstance(snapshot, dict):
            grounding = snapshot.get("grounding", {})
            if grounding:
                return grounding
        decision = context.get("_decision", "")
        try:
            static_grounding = get_grounding_data(decision, context)
            return static_grounding
        except Exception:
            role = context.get("role", "software engineer")
            location = normalise_location(context.get("location", "India"))
            return {
                "role": role, "industry": context.get("industry", "default"),
                "location": location,
                "salary_entry_lpa": None, "salary_mid_lpa": None, "salary_senior_lpa": None,
                "employment_rate": None, "cost_of_living_index": None,
                "cost_of_living_source": "unavailable", "salary_source": "unavailable",
                "data_source": None, "live_cpi": None, "live_unemployment": None,
                "live_gdp_growth": None, "confidence": None,
            }

    def _build_economic_data(self, context: Dict[str, Any], override: Optional[Dict] = None) -> EconomicData:
        snapshot = context.get("_economic_snapshot", {})
        grounding = snapshot.get("grounding", {}) if isinstance(snapshot, dict) else {}
        if not grounding:
            try:
                grounding = get_grounding_data(context.get("_decision", ""), context)
            except Exception:
                grounding = {}
        live_gdp = grounding.get("live_gdp_growth")
        live_cpi = grounding.get("live_cpi")
        live_unemp = grounding.get("live_unemployment")
        col_index = float(grounding.get("cost_of_living_index", 1.2))
        salary_growth = float(grounding.get("salary_growth_pct", context.get("salary_growth_pct", 7.5)))
        industry_health = float(grounding.get("industry_health", context.get("industry_health", 78.0)))
        data = EconomicData(
            gdp_growth=float(live_gdp if live_gdp is not None else context.get("gdp_growth", 6.5)),
            inflation_cpi=float(live_cpi if live_cpi is not None else context.get("inflation_cpi", 5.0)),
            unemployment_rate=float(live_unemp if live_unemp is not None else context.get("unemployment_rate", 4.2)),
            salary_growth_pct=salary_growth, industry_health=industry_health,
            cost_of_living_index=col_index,
            automation_risk=float(context.get("automation_risk", 15.0)),
            interest_rate=float(context.get("interest_rate", 6.5)),
            data_confidence=float(snapshot.get("confidence", 85)) / 100.0 if isinstance(snapshot, dict) else 0.85,
            data_sources={}, data_freshness={},
        )
        if override:
            for k, v in override.items():
                if hasattr(data, k):
                    setattr(data, k, v)
        return data

    def _run_agents(
        self,
        decision: str,
        profile: UserProfile,
        economic: EconomicData,
        future_paths: Dict[str, FuturePath],
        options: List[DecisionOption],
    ) -> Dict[str, AgentOutput]:
        results = {}
        logger.info("[Pipeline] Running %d agents in parallel...", len(self.agents))
        with ThreadPoolExecutor(max_workers=len(self.agents)) as ex:
            futures = {
                ex.submit(a.analyze, decision, profile, economic, future_paths, options): name
                for name, a in self.agents.items()
            }
            for f in as_completed(futures):
                name = futures[f]
                try:
                    output = f.result()
                    results[name] = output
                    logger.info("[Pipeline] Agent '%s' score=%.1f conf=%.1f options=%s",
                                name, output.score, output.confidence,
                                list(output.per_option_scores.keys()) if output.per_option_scores else [])
                except Exception as e:
                    logger.error("Agent '%s' failed: %s", name, e)
                    results[name] = AgentOutput(agent_name=name, score=50, confidence=0, reasoning=f"Agent failed: {e}")
        return results

    def _get_missing_data(self, economic: EconomicData) -> list:
        missing = []
        if not economic.data_sources:
            missing.append("economic_sources")
        if economic.data_confidence < 0.3:
            missing.append("economic_data")
        missing_count = sum(1 for v in economic.data_freshness.values() if v == "static_estimate")
        if missing_count > 3:
            missing.append("multiple_static_estimates")
        return missing

    def _generate_warnings(self, parsed: dict, economic: EconomicData, confidence: ConfidenceBreakdown, real_data: Any) -> list:
        warnings = []
        if parsed.get("confidence", 100) < 50:
            warnings.append("Decision could not be confidently parsed. Results may not fully reflect your question.")
        if confidence.overall < 40:
            warnings.append("Overall confidence is low. Consider providing more context for better accuracy.")
        if economic.data_confidence < 0.5:
            warnings.append("Economic data confidence is low. Results based on limited real-world data.")
        if real_data.data_completeness < 0.4:
            warnings.append(f"Only {int(real_data.data_completeness * 100)}% of data sources have live data.")
        return warnings

    def get_pivot(self, original_result: SimulationResult, timeline_key: str, event_year: str, alternative_outcome: str) -> Any:
        return compute_pivot(
            profile=original_result.user_profile,
            economic=original_result.economic_data,
            original_timeline=original_result.future_paths.get(timeline_key, FuturePath()),
            event_year=event_year,
            alternative_outcome=alternative_outcome,
            agent_outputs=original_result.agent_outputs,
        )


def _future_to_timeline_like(fp: FuturePath) -> Any:
    class TimelineLike:
        pass
    tl = TimelineLike()
    tl.key = fp.option_key
    tl.archetype = fp.archetype
    tl.final_score = fp.final_score
    tl.regret = ""
    tl.letter = ""
    tl.events = fp.events
    tl.years = {k: _ys_to_old(v) for k, v in fp.years.items()}
    return tl


def _ys_to_old(ys) -> Any:
    class YS:
        pass
    o = YS()
    o.income = ys.income
    o.career_growth = ys.career_growth
    o.stress = ys.stress
    o.health = ys.health
    o.relationships = ys.relationships
    o.happiness = ys.happiness
    o.opportunity = ys.opportunity
    o.savings = ys.savings
    o.net_worth = ys.net_worth
    o.risk_exposure = ys.risk_exposure
    return o
