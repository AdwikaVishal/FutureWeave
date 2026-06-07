from __future__ import annotations
import logging
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from models_v2 import SimulationV2, TimelineRow, AgentOutputRow, MonteCarloRun, PivotEvent, User
from decision_engine import DecisionPipeline, SimulationResult

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v2")
pipeline = DecisionPipeline()


class SimulateRequest(BaseModel):
    decision: str
    context: Dict[str, Any] = {}
    economic_override: Optional[Dict[str, Any]] = None
    enable_monte_carlo: bool = True
    monte_carlo_iterations: int = 10000
    user_email: Optional[str] = None


class PivotRequest(BaseModel):
    simulation_id: str
    timeline_key: str
    event_year: str
    alternative_outcome: str


def _get_db():
    from models_v2 import init_db_v2
    from sqlalchemy.orm import sessionmaker
    engine = init_db_v2()
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/simulate")
async def simulate(request: SimulateRequest):
    try:
        result: SimulationResult = pipeline.run(
            decision=request.decision,
            context=request.context,
            economic_override=request.economic_override,
            enable_monte_carlo=request.enable_monte_carlo,
            monte_carlo_iterations=request.monte_carlo_iterations,
        )
        return _result_to_dict(result)
    except Exception as e:
        logger.error("Simulation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulate-and-save")
async def simulate_and_save(request: SimulateRequest, db: Session = Depends(_get_db)):
    try:
        result = pipeline.run(
            decision=request.decision,
            context=request.context,
            economic_override=request.economic_override,
            enable_monte_carlo=request.enable_monte_carlo,
            monte_carlo_iterations=request.monte_carlo_iterations,
        )
        _persist_simulation(db, result, request.user_email)
        return _result_to_dict(result)
    except Exception as e:
        logger.error("Simulation + save failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pivot")
async def pivot(request: PivotRequest, db: Session = Depends(_get_db)):
    try:
        sim_row = db.query(SimulationV2).filter(SimulationV2.id == request.simulation_id).first()
        if not sim_row:
            raise HTTPException(status_code=404, detail="Simulation not found")
        original_timelines = sim_row.timelines
        tl = next((t for t in original_timelines if t.key == request.timeline_key), None)
        if not tl:
            raise HTTPException(status_code=404, detail="Timeline not found")
        original_result = _rebuild_result(sim_row)
        pivot_result = pipeline.get_pivot(
            original_result=original_result,
            timeline_key=request.timeline_key,
            event_year=request.event_year,
            alternative_outcome=request.alternative_outcome,
        )
        pe = PivotEvent(
            simulation_id=request.simulation_id,
            original_timeline_key=request.timeline_key,
            event_year=request.event_year,
            alternative_outcome=request.alternative_outcome,
            deltas=pivot_result.deltas,
            agent_changes=pivot_result.agent_changes,
            confidence_change=pivot_result.confidence_change,
        )
        db.add(pe)
        db.commit()
        return {
            "original_timeline": _futurepath_to_dict(pivot_result.original_timeline),
            "pivoted_timeline": _futurepath_to_dict(pivot_result.pivoted_timeline),
            "deltas": pivot_result.deltas,
            "agent_changes": pivot_result.agent_changes,
            "confidence_change": pivot_result.confidence_change,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Pivot failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/simulation/{simulation_id}")
async def get_simulation(simulation_id: str, db: Session = Depends(_get_db)):
    sim = db.query(SimulationV2).filter(SimulationV2.id == simulation_id).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": sim.id,
        "decision": sim.decision,
        "decision_parsing": sim.decision_parsing,
        "confidence_overall": sim.confidence_overall,
        "confidence_tier": sim.confidence_tier,
        "timelines": [_timeline_row_to_dict(t) for t in sim.timelines],
        "agent_outputs": [_agent_row_to_dict(a) for a in sim.agent_outputs],
        "monte_carlo": [_mc_row_to_dict(m) for m in sim.monte_carlo_runs],
        "created_at": sim.created_at.isoformat() if sim.created_at else None,
    }


@router.get("/health")
async def health_v2():
    return {"status": "healthy", "version": "2.0", "timestamp": datetime.utcnow().isoformat()}


def _result_to_dict(result: SimulationResult) -> dict:
    return {
        "simulation_id": result.simulation_id,
        "decision": result.decision,
        "decision_parsing": result.decision_parsing,
        "user_profile": _profile_to_dict(result.user_profile),
        "economic_data": _economic_to_dict(result.economic_data),
        "options": [_option_to_dict(o) for o in result.options],
        "future_paths": {k: _futurepath_to_dict(v) for k, v in result.future_paths.items()},
        "agent_outputs": {k: _agent_output_to_dict(v) for k, v in result.agent_outputs.items()},
        "debate_result": _debate_to_dict(result.debate_result) if result.debate_result else None,
        "monte_carlo": _monte_carlo_to_dict(result.monte_carlo) if result.monte_carlo else None,
        "confidence": _confidence_to_dict(result.confidence),
        "regret_analysis": _regret_to_dict(result.regret_analysis) if result.regret_analysis else None,
        "life_dashboard": _dashboard_to_dict(result.life_dashboard) if result.life_dashboard else None,
        "causal_graph": _causal_to_dict(result.causal_graph) if result.causal_graph else None,
        "warnings": result.warnings,
        "real_data_scores": result.real_data_scores,
        "data_sources_used": result.data_sources_used,
        "data_freshness": result.data_freshness,
        "economic_indicators": result.economic_indicators,
    }


def _profile_to_dict(p) -> dict:
    return {
        "age": p.age, "location": p.location, "risk_tolerance": p.risk_tolerance,
        "savings": p.savings, "dependents": p.dependents, "skills": p.skills,
        "industry": p.industry, "role": p.role,
        "relationship_status": p.relationship_status, "has_children": p.has_children,
        "children_count": p.children_count, "health_condition": p.health_condition,
        "debt_amount": p.debt_amount, "current_salary": p.current_salary,
        "education_level": p.education_level, "years_experience": p.years_experience,
        "monthly_savings": p.monthly_savings,
    }


def _economic_to_dict(e) -> dict:
    return {
        "gdp_growth": e.gdp_growth, "inflation_cpi": e.inflation_cpi,
        "unemployment_rate": e.unemployment_rate, "salary_growth_pct": e.salary_growth_pct,
        "industry_health": e.industry_health, "automation_risk": e.automation_risk,
        "interest_rate": e.interest_rate, "data_confidence": e.data_confidence,
        "cost_of_living_index": e.cost_of_living_index,
        "economic_score": e.economic_score, "employment_score": e.employment_score,
        "industry_score": e.industry_score, "cost_of_living_score": e.cost_of_living_score,
        "salary_score": e.salary_score,
    }


def _option_to_dict(o) -> dict:
    return {
        "title": o.title, "description": o.description,
        "risk_level": o.risk_level, "time_horizon": o.time_horizon,
        "upside_potential": o.upside_potential, "downside_risk": o.downside_risk,
    }


def _futurepath_to_dict(p) -> dict:
    return {
        "option_key": p.option_key, "label": p.label,
        "archetype": p.archetype, "final_score": p.final_score,
        "years": {k: _year_scores_to_dict(v) for k, v in p.years.items()},
        "events": p.events, "summary": p.summary,
        "best_case": p.best_case, "expected_case": p.expected_case,
        "worst_case": p.worst_case,
    }


def _year_scores_to_dict(y) -> dict:
    return {
        "income": y.income, "career_growth": y.career_growth, "stress": y.stress,
        "health": y.health, "relationships": y.relationships, "happiness": y.happiness,
        "opportunity": y.opportunity, "savings": y.savings, "net_worth": y.net_worth,
        "risk_exposure": y.risk_exposure, "purpose": y.purpose, "freedom": y.freedom,
        "regret": y.regret, "burnout_risk": y.burnout_risk,
        "learning_growth": y.learning_growth, "social_support": y.social_support,
    }


def _agent_output_to_dict(a) -> dict:
    return {
        "agent_name": a.agent_name, "score": a.score, "confidence": a.confidence,
        "reasoning": a.reasoning, "evidence": a.evidence,
        "assumptions": a.assumptions, "risks": a.risks, "opportunities": a.opportunities,
        "recommendation": a.recommendation, "impact": a.impact,
        "year_scores": a.year_scores,
        "score_changes": a.score_changes, "data_used": a.data_used,
        "impact_factors": a.impact_factors,
        "per_option_scores": a.per_option_scores,
        "option_rankings": a.option_rankings,
        "tension_with": a.tension_with, "verdict": a.verdict,
    }


def _debate_to_dict(d) -> dict:
    return {
        "entries": [{
            "topic": e.topic, "agents_involved": e.agents_involved,
            "positions": e.positions, "consensus_score": e.consensus_score,
            "disagreement_score": e.disagreement_score,
            "tension_score": getattr(e, "tension_score", e.disagreement_score),
            "resolution": e.resolution,
            "key_tension_pair": list(getattr(e, "key_tension_pair", ("", ""))),
            "root_cause": getattr(e, "root_cause", ""),
        } for e in d.entries],
        "voting_matrix": d.voting_matrix,
        "consensus_summary": d.consensus_summary,
        "overall_tension_score": getattr(d, "overall_tension_score", 0),
        "primary_disagreement": getattr(d, "primary_disagreement", ""),
        "agent_alliances": getattr(d, "agent_alliances", []),
    }


def _monte_carlo_to_dict(m) -> dict:
    return {
        "iterations": m.iterations,
        "node_distributions": m.node_distributions,
        "percentiles": m.percentiles,
        "success_probability": m.success_probability,
        "failure_probability": m.failure_probability,
        "risk_metrics": m.risk_metrics,
        "timeline_comparison": m.timeline_comparison,
        "best_case": m.best_case, "expected_case": m.expected_case,
        "worst_case": m.worst_case,
        "regret_probability": getattr(m, "regret_probability", 0),
        "opportunity_cost": getattr(m, "opportunity_cost", 0),
        "path_dependencies": getattr(m, "path_dependencies", {}),
    }


def _confidence_to_dict(c) -> dict:
    return {
        "overall": c.overall, "agent_agreement": c.agent_agreement,
        "data_quality": c.data_quality, "simulation_stability": c.simulation_stability,
        "economic_certainty": c.economic_certainty,
        "historical_similarity": c.historical_similarity,
        "missing_data_penalty": c.missing_data_penalty,
        "data_freshness_score": c.data_freshness_score,
        "data_completeness_score": c.data_completeness_score,
        "per_aspect": c.per_aspect, "per_agent": c.per_agent,
        "uncertainty_drivers": c.uncertainty_drivers, "tier": c.tier,
    }


def _regret_to_dict(r) -> dict:
    return {
        "will_regret_not_trying": r.will_regret_not_trying,
        "will_regret_risk": r.will_regret_risk,
        "will_regret_delaying": r.will_regret_delaying,
        "will_regret_comfort": r.will_regret_comfort,
        "overall_regret_risk": r.overall_regret_risk,
        "regret_timeline": r.regret_timeline,
        "biggest_regret_source": r.biggest_regret_source,
        "regret_letter": r.regret_letter,
        "by_option": r.by_option,
    }


def _dashboard_to_dict(d) -> dict:
    return {
        "life_satisfaction": d.life_satisfaction,
        "freedom_index": d.freedom_index,
        "stress_index": d.stress_index,
        "purpose_index": d.purpose_index,
        "wealth_index": d.wealth_index,
        "relationship_index": d.relationship_index,
        "growth_index": d.growth_index,
        "regret_risk": d.regret_risk,
        "decision_confidence": d.decision_confidence,
        "dimension_breakdown": d.dimension_breakdown,
        "overall_score": d.overall_score,
        "trend": d.trend,
        "primary_concern": d.primary_concern,
        "top_opportunity": d.top_opportunity,
    }


def _causal_to_dict(c) -> dict:
    return {
        "nodes": c.nodes,
        "edges": [{"source": e.source, "target": e.target, "strength": e.strength,
                    "effect_type": e.effect_type, "description": e.description} for e in c.edges],
        "positive_loops": c.positive_loops, "negative_loops": c.negative_loops,
    }


def _persist_simulation(db: Session, result: SimulationResult, user_email: Optional[str] = None):
    user_id = None
    if user_email:
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            user = User(email=user_email)
            db.add(user)
            db.flush()
        user_id = user.id
    sim = SimulationV2(
        id=result.simulation_id, user_id=user_id, decision=result.decision,
        decision_parsing=result.decision_parsing,
        user_profile=_profile_to_dict(result.user_profile),
        economic_data=_economic_to_dict(result.economic_data),
        confidence_overall=result.confidence.overall,
        confidence_tier=result.confidence.tier,
    )
    db.add(sim)
    for key, path in result.future_paths.items():
        row = TimelineRow(
            simulation_id=sim.id, key=path.option_key, archetype=path.archetype,
            final_score=path.final_score, events=path.events,
            year1_data=_year_scores_to_dict(path.years.get("Year1", {})),
            year3_data=_year_scores_to_dict(path.years.get("Year3", {})),
            year5_data=_year_scores_to_dict(path.years.get("Year5", {})),
            year10_data=_year_scores_to_dict(path.years.get("Year10", {})),
        )
        db.add(row)
    for name, ao in result.agent_outputs.items():
        row = AgentOutputRow(
            simulation_id=sim.id, agent_name=ao.agent_name, score=ao.score,
            confidence=ao.confidence, reasoning=ao.reasoning, evidence=ao.evidence,
            assumptions=ao.assumptions, risks=ao.risks, opportunities=ao.opportunities,
            recommendation=ao.recommendation, impact=ao.impact, year_scores=ao.year_scores,
        )
        db.add(row)
    if result.monte_carlo:
        mc = result.monte_carlo
        mc_row = MonteCarloRun(
            simulation_id=sim.id, iterations=mc.iterations,
            node_distributions=mc.node_distributions, percentiles=mc.percentiles,
            success_probability=mc.success_probability,
            failure_probability=mc.failure_probability,
            risk_metrics=mc.risk_metrics,
            timeline_comparison=mc.timeline_comparison,
        )
        db.add(mc_row)
    db.commit()


def _rebuild_result(sim_row: SimulationV2) -> SimulationResult:
    from decision_engine.types import SimulationResult as SR
    from decision_engine.types import FuturePath, YearScores, AgentOutput, ConfidenceBreakdown, EconomicData, UserProfile, DecisionOption
    future_paths = {}
    for t in sim_row.timelines:
        years = {}
        year_data_map = {"Year1": t.year1_data, "Year3": t.year3_data, "Year5": t.year5_data, "Year10": t.year10_data}
        for yk, yd in year_data_map.items():
            if yd:
                years[yk] = YearScores(**{k: yd.get(k, 50) for k in
                    ["income", "career_growth", "stress", "health", "relationships",
                     "happiness", "opportunity", "savings", "net_worth", "risk_exposure",
                     "purpose", "freedom", "regret", "burnout_risk", "learning_growth", "social_support"]})
        future_paths[t.key] = FuturePath(
            option_key=t.key, label=t.archetype, years=years,
            events=t.events or [], final_score=t.final_score or 50,
        )
    agent_outputs = {}
    for a in sim_row.agent_outputs:
        agent_outputs[a.agent_name] = AgentOutput(
            agent_name=a.agent_name, score=a.score or 50, confidence=a.confidence or 0,
            reasoning=a.reasoning or "", evidence=a.evidence or [],
            assumptions=a.assumptions or [], risks=a.risks or [],
            opportunities=a.opportunities or [], recommendation=a.recommendation or "",
            impact=a.impact or "neutral", year_scores=a.year_scores or {},
        )
    return SR(
        decision=sim_row.decision, decision_parsing=sim_row.decision_parsing or {},
        future_paths=future_paths, agent_outputs=agent_outputs,
        confidence=ConfidenceBreakdown(overall=sim_row.confidence_overall or 0, tier=sim_row.confidence_tier or "low"),
    )


def _timeline_row_to_dict(t) -> dict:
    return {"key": t.key, "archetype": t.archetype, "final_score": t.final_score,
            "year1": t.year1_data, "year3": t.year3_data, "year5": t.year5_data,
            "year10": t.year10_data, "events": t.events}


def _agent_row_to_dict(a) -> dict:
    return {"agent_name": a.agent_name, "score": a.score, "confidence": a.confidence,
            "reasoning": a.reasoning, "evidence": a.evidence, "assumptions": a.assumptions,
            "risks": a.risks, "opportunities": a.opportunities,
            "recommendation": a.recommendation, "impact": a.impact, "year_scores": a.year_scores}


def _mc_row_to_dict(m) -> dict:
    return {"iterations": m.iterations, "node_distributions": m.node_distributions,
            "percentiles": m.percentiles, "success_probability": m.success_probability}
