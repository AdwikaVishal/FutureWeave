from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import os

from models import init_db, get_db, Simulation, FollowUp, CounsellorNote
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Decision Simulation Engine",
    version="1.0.0",
)

# ✅ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ SAFE startup
@app.on_event("startup")
def startup_event():
    try:
        init_db()
        print("[Startup] DB initialized")
    except Exception as e:
        print(f"[Startup ERROR] {e}")

# ✅ Health route (VERY IMPORTANT)
@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "healthy", "time": datetime.utcnow().isoformat()}


# =========================
# MODELS
# =========================

class SimulateRequest(BaseModel):
    decision: str
    context: Dict[str, Any]
    user_email: Optional[str] = None


# =========================
# MAIN ENDPOINT
# =========================

@app.post("/simulate")
async def simulate(request: SimulateRequest, db: Session = Depends(get_db)):
    try:
        decision = request.decision
        context = request.context

        # ✅ LAZY IMPORTS (CRITICAL FIX)
        from agents.timeline import generate_timelines, TIMELINE_KEYS
        from agents.chaos import apply_chaos
        from agents.synthesis import batch_synthesis

        # 1. Generate timelines
        timelines_raw = generate_timelines(decision, context)
        analysis = timelines_raw.pop("_analysis", {})

        # 2. Chaos
        chaos_events = {}
        for tl in TIMELINE_KEYS:
            year1 = timelines_raw.get(tl, {}).get("_causal", {}).get("Year1", {})
            chaos_events[tl] = apply_chaos(year1, personality_key=tl[-1]).get("events", [])

        timelines_raw = generate_timelines(decision, context, chaos_events=chaos_events)

        # 3. Clean timelines
        timelines = {}
        for name, tl in timelines_raw.items():
            if not name.startswith("_"):
                timelines[name] = tl

        # 4. Synthesis
        synthesis = batch_synthesis(timelines, decision, context)

        # 5. Save
        sim = Simulation(
            user_email=request.user_email,
            decision=decision,
            context=context,
            timelines=timelines,
            regrets=synthesis.get("regrets", {}),
            comparison=synthesis.get("comparison", {}),
            letters=synthesis.get("letters", {}),
        )

        db.add(sim)
        db.commit()
        db.refresh(sim)

        return {
            "simulation_id": sim.id,
            "timelines": timelines,
            "analysis": analysis,
            "regrets": synthesis.get("regrets", {}),
            "letters": synthesis.get("letters", {}),
            "comparison": synthesis.get("comparison", {}),
        }

    except Exception as e:
        print("[ERROR]", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# EXTRA ENDPOINTS
# =========================

@app.get("/simulation/{simulation_id}")
def get_simulation(simulation_id: int, db: Session = Depends(get_db)):
    sim = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Not found")
    return sim.to_dict()


@app.post("/followup")
def followup(simulation_id: int, actual_timeline: str, db: Session = Depends(get_db)):
    sim = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    f = FollowUp(
        simulation_id=simulation_id,
        actual_timeline=actual_timeline,
    )
    db.add(f)
    db.commit()

    return {"status": "ok"}


# =========================
# PIVOT
# =========================

class PivotRequest(BaseModel):
    original_timeline: Dict[str, Any]
    event_year: int
    alternative_outcome: str
    decision: str
    context: Dict[str, Any]

@app.post("/pivot")
async def pivot(request: PivotRequest):
    try:
        from agents.timeline import generate_pivot_timeline
        from agents.synthesis import _fallback_regret, _fallback_letter

        new_timeline = generate_pivot_timeline(
            original_timeline=request.original_timeline,
            event_year=request.event_year,
            alternative_outcome=request.alternative_outcome,
            decision=request.decision,
            context=request.context,
        )
        narrative_only = {k: v for k, v in new_timeline.items() if not k.startswith("_")}
        causal = new_timeline.get("_causal", {})
        pivot_tl = {**narrative_only, "_causal": causal}
        regret = _fallback_regret("pivot", pivot_tl)
        letter = _fallback_letter("pivot", pivot_tl, regret)
        return {"new_timeline": narrative_only, "regret": regret, "letter": letter}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# SCORE
# =========================

class ScoreRequest(BaseModel):
    simulation_id: int
    weights: Dict[str, float]

@app.post("/score")
async def score(request: ScoreRequest, db: Session = Depends(get_db)):
    sim = db.query(Simulation).filter(Simulation.id == request.simulation_id).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    weights = request.weights
    total_w = sum(weights.values())
    if total_w <= 0:
        raise HTTPException(status_code=400, detail="Weights must be positive")
    weights = {k: v / total_w for k, v in weights.items()}

    try:
        from agents.timeline import generate_timelines
        timelines_raw = generate_timelines(sim.decision, sim.context)
        causal_data = {
            name: tl.get("_causal", {})
            for name, tl in timelines_raw.items()
            if not name.startswith("_")
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Could not retrieve causal data")

    YEAR_WEIGHTS = {"Year1": 0.1, "Year3": 0.2, "Year5": 0.3, "Year10": 0.4}
    scores = {}
    for tl_name, causal in causal_data.items():
        weighted_sum = 0.0
        for yr, yr_w in YEAR_WEIGHTS.items():
            yr_scores = causal.get(yr, {})
            yr_score = sum(yr_scores.get(n, 50) * w for n, w in weights.items() if n in yr_scores)
            weighted_sum += yr_score * yr_w
        scores[tl_name] = round(weighted_sum, 1)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return {
        "scores": scores,
        "ranked": [{"timeline": t, "score": s} for t, s in ranked],
        "recommendation": ranked[0][0] if ranked else None,
        "weights_used": weights,
    }


# =========================
# PEER COMPARISON
# =========================

@app.get("/peer-comparison")
async def peer_comparison(
    decision_keywords: str = Query(""),
    db: Session = Depends(get_db),
):
    followups = db.query(FollowUp).filter(FollowUp.actual_timeline.isnot(None)).all()
    if not followups:
        return {"message": "No follow-up data yet", "stats": {}, "total": 0}

    keywords = [k.strip().lower() for k in decision_keywords.split(",") if k.strip()]
    matched = []
    for fu in followups:
        sim = db.query(Simulation).filter(Simulation.id == fu.simulation_id).first()
        if sim and (not keywords or any(kw in sim.decision.lower() for kw in keywords)):
            matched.append(fu)
    if not matched:
        matched = followups

    total = len(matched)
    counts: Dict[str, int] = {}
    for fu in matched:
        tl = fu.actual_timeline or "Unknown"
        counts[tl] = counts.get(tl, 0) + 1

    stats = {tl: {"count": c, "pct": round(c / total * 100, 1)} for tl, c in counts.items()}
    return {
        "stats": stats,
        "total": total,
        "message": f"Based on {total} anonymised follow-up{'s' if total != 1 else ''} from similar decisions.",
    }


# =========================
# COMPARE TWO
# =========================

class CompareTwoRequest(BaseModel):
    decision_a: str
    decision_b: str
    context: Dict[str, Any]
    user_email: Optional[str] = None

@app.post("/compare-two")
async def compare_two(request: CompareTwoRequest, db: Session = Depends(get_db)):
    try:
        from agents.timeline import generate_timelines, TIMELINE_KEYS
        from agents.synthesis import batch_synthesis

        results = {}
        for label, decision in [("A", request.decision_a), ("B", request.decision_b)]:
            timelines_raw = generate_timelines(decision, request.context)
            analysis = timelines_raw.pop("_analysis", {})

            causal_data, interpretations, grounding_meta, computed_meta, timelines = {}, {}, {}, {}, {}
            for name, tl in timelines_raw.items():
                if name.startswith("_"):
                    continue
                causal_data[name]     = tl.pop("_causal", {})
                interpretations[name] = tl.pop("_interpretations", {})
                grounding_meta[name]  = tl.pop("_grounding", {})
                computed_meta[name]   = tl.pop("_computed", {})
                timelines[name]       = tl

            synthesis = batch_synthesis(timelines, decision, request.context)

            sim = Simulation(
                user_email=request.user_email,
                decision=decision,
                context=request.context,
                timelines=timelines,
                regrets=synthesis.get("regrets", {}),
                comparison=synthesis.get("comparison", {}),
                letters=synthesis.get("letters", {}),
            )
            db.add(sim)
            db.commit()
            db.refresh(sim)

            results[label] = {
                "simulation_id": sim.id,
                "decision": decision,
                "timelines": timelines,
                "causal_data": causal_data,
                "interpretations": interpretations,
                "grounding": grounding_meta,
                "computed": computed_meta,
                "regrets": synthesis.get("regrets", {}),
                "letters": synthesis.get("letters", {}),
                "comparison": synthesis.get("comparison", {}),
                "analysis": analysis,
            }

        return {"decision_a": results["A"], "decision_b": results["B"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# COUNSELLOR DASHBOARD
# =========================

class CounsellorNoteRequest(BaseModel):
    simulation_id: int
    counsellor_email: str
    note: str

@app.get("/counsellor/students")
async def counsellor_students(
    counsellor_email: str = Query(...),
    db: Session = Depends(get_db),
):
    sims = db.query(Simulation).order_by(Simulation.created_at.desc()).limit(200).all()
    result = []
    for sim in sims:
        notes = db.query(CounsellorNote).filter(CounsellorNote.simulation_id == sim.id).all()
        result.append({
            "simulation_id": sim.id,
            "user_email": sim.user_email or "anonymous",
            "decision": sim.decision,
            "context": sim.context,
            "created_at": sim.created_at.isoformat() if sim.created_at else None,
            "timeline_count": len(sim.timelines),
            "notes": [n.to_dict() for n in notes],
        })
    return {"students": result, "total": len(result)}

@app.post("/counsellor/note")
async def add_counsellor_note(request: CounsellorNoteRequest, db: Session = Depends(get_db)):
    sim = db.query(Simulation).filter(Simulation.id == request.simulation_id).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    note = CounsellorNote(
        simulation_id=request.simulation_id,
        counsellor_email=request.counsellor_email,
        note=request.note,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {"status": "ok", "note_id": note.id}


# =========================
# JOB MARKET
# =========================

@app.get("/job-market")
async def job_market(
    role: str = Query("software engineer"),
    location: str = Query("Bangalore"),
    skills: str = Query(""),
):
    try:
        from data_grounding import detect_role, normalise_location
        from real_data_provider import get_ambitionbox_salary, get_worldbank_unemployment, get_worldbank_gdp_growth
        norm_location = normalise_location(location)
        norm_role = detect_role(role, {})
        salary_range = get_ambitionbox_salary(norm_role, norm_location)
        unemployment = get_worldbank_unemployment()
        gdp_growth = get_worldbank_gdp_growth()
    except Exception:
        norm_role = role
        norm_location = location
        salary_range = [8, 25]
        unemployment = 7.5
        gdp_growth = 6.5

    SKILL_DEMAND = {
        "python": {"growth_pct": 22, "jobs_india": 45000, "trend": "rising"},
        "javascript": {"growth_pct": 15, "jobs_india": 60000, "trend": "stable"},
        "react": {"growth_pct": 18, "jobs_india": 35000, "trend": "rising"},
        "machine learning": {"growth_pct": 35, "jobs_india": 20000, "trend": "rising"},
        "data analysis": {"growth_pct": 28, "jobs_india": 30000, "trend": "rising"},
        "java": {"growth_pct": 5, "jobs_india": 55000, "trend": "stable"},
        "sql": {"growth_pct": 12, "jobs_india": 40000, "trend": "stable"},
        "aws": {"growth_pct": 30, "jobs_india": 25000, "trend": "rising"},
        "devops": {"growth_pct": 25, "jobs_india": 18000, "trend": "rising"},
        "product management": {"growth_pct": 20, "jobs_india": 12000, "trend": "rising"},
    }
    skill_list = [s.strip() for s in skills.split(",") if s.strip()]
    skill_insights = {}
    for skill in skill_list:
        key = skill.lower()
        for sk, data in SKILL_DEMAND.items():
            if sk in key or key in sk:
                skill_insights[skill] = {**data, "source": "static_2024"}
                break
        if skill not in skill_insights:
            skill_insights[skill] = {"growth_pct": None, "trend": "unknown", "source": "no_data"}

    return {
        "role": norm_role,
        "location": norm_location,
        "salary_range_lpa": salary_range,
        "unemployment_pct": unemployment,
        "gdp_growth_pct": gdp_growth,
        "skill_demand": skill_insights,
    }


# =========================
# OUTCOMES LIBRARY
# =========================

@app.get("/outcomes")
async def outcomes(limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    followups = (
        db.query(FollowUp)
        .filter(FollowUp.actual_timeline.isnot(None))
        .order_by(FollowUp.created_at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for fu in followups:
        sim = db.query(Simulation).filter(Simulation.id == fu.simulation_id).first()
        if not sim:
            continue
        ctx = dict(sim.context)
        result.append({
            "decision_preview": sim.decision[:80] + ("..." if len(sim.decision) > 80 else ""),
            "context": {"age": ctx.get("age"), "location": ctx.get("location"), "risk_tolerance": ctx.get("risk_tolerance")},
            "chosen_timeline": fu.actual_timeline,
            "feedback_preview": (fu.feedback or "")[:120],
            "months_after": int((fu.created_at - sim.created_at).days / 30) if fu.created_at and sim.created_at else None,
        })

    total = db.query(FollowUp).filter(FollowUp.actual_timeline.isnot(None)).count()
    tl_counts: Dict[str, int] = {}
    for fu in db.query(FollowUp).filter(FollowUp.actual_timeline.isnot(None)).all():
        tl = fu.actual_timeline or "Unknown"
        tl_counts[tl] = tl_counts.get(tl, 0) + 1

    return {"outcomes": result, "aggregate": {"total_followups": total, "timeline_distribution": tl_counts}}
