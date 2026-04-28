"""
FastAPI backend for the Decision Simulation Engine.

Endpoints:
  POST /simulate              - Run full simulation pipeline
  GET  /health                - Health check
  POST /pivot                 - Branch a timeline at a specific event
  GET  /followup/{id}         - Get follow-up page data
  POST /followup              - Submit follow-up response
  POST /score                 - Personalised weighted score for timelines
  GET  /peer-comparison       - Anonymised peer outcome stats
  POST /compare-two           - Side-by-side comparison of two decisions
  GET  /counsellor/students   - Counsellor dashboard: all student simulations
  POST /counsellor/note       - Add counsellor note to a simulation
  GET  /job-market            - Live job market demand for skills
  GET  /outcomes              - Public anonymised outcome library
  GET  /data-sources          - Data source badge registry
"""
from fastapi import FastAPI, HTTPException, Depends, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime
import hashlib
import json
import logging
import os

logger = logging.getLogger(__name__)

# Import simulation agents
from agents.timeline import generate_timelines, generate_pivot_timeline, TIMELINE_KEYS
from agents.chaos import apply_chaos
from agents.synthesis import batch_synthesis
from agents.regret import analyze_regret
from agents.comparator import compare_timelines
from agents.letter import write_future_letter

# Import database models
from models import init_db, get_db, Simulation, FollowUp, CounsellorNote, OutcomeRecord
from sqlalchemy.orm import Session

# Import Celery tasks (optional)
try:
    from tasks import schedule_followup
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

# Initialize database tables
init_db()

app = FastAPI(
    title="Decision Simulation Engine",
    description="REST API for simulating decision outcomes across multiple timelines",
    version="1.0.0",
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response Models ---

class SimulateRequest(BaseModel):
    decision: str
    context: Dict[str, Any]
    user_email: Optional[str] = None


class SimulateResponse(BaseModel):
    simulation_id: int
    timelines: Dict[str, Any]
    causal_data: Dict[str, Any]
    interpretations: Dict[str, Any]
    grounding: Dict[str, Any]
    computed: Dict[str, Any]
    analysis: Dict[str, Any]
    regrets: Dict[str, Any]
    letters: Dict[str, Any]
    comparison: Dict[str, Any]


class PivotRequest(BaseModel):
    original_timeline: Dict[str, Any]  # values can be strings or nested dicts (_causal etc.)
    event_year: int
    alternative_outcome: str
    decision: str
    context: Dict[str, Any]


class PivotResponse(BaseModel):
    new_timeline: Dict[str, Any]
    regret: Dict[str, str]
    letter: str


class FollowUpRequest(BaseModel):
    simulation_id: int
    actual_timeline: str
    feedback: Optional[str] = None
    user_email: Optional[str] = None


class ScoreRequest(BaseModel):
    simulation_id: int
    weights: Dict[str, float]  # e.g. {"income": 0.7, "happiness": 0.3}


class CompareTwoRequest(BaseModel):
    decision_a: str
    decision_b: str
    context: Dict[str, Any]
    user_email: Optional[str] = None


class CounsellorNoteRequest(BaseModel):
    simulation_id: int
    counsellor_email: str
    note: str


# --- Endpoints ---

@app.post("/simulate", response_model=SimulateResponse)
async def simulate(request: SimulateRequest, db: Session = Depends(get_db)):
    """
    Run the full simulation pipeline:
    1. Generate timelines
    2. Apply chaos
    3. Analyze regret
    4. Compare timelines
    5. Write future letters
    6. Save to database
    7. Schedule follow-up email (if Celery available)
    """
    try:
        decision = request.decision
        context = request.context

        # 1. Generate timelines (1 LLM call, cached)
        timelines_raw = generate_timelines(decision, context)
        analysis      = timelines_raw.pop("_analysis", {})

        # 2. Apply chaos (deterministic — no LLM)
        chaos_events = {}
        for tl in TIMELINE_KEYS:
            year1_scores = timelines_raw.get(tl, {}).get("_causal", {}).get("Year1", {})
            chaos_events[tl] = apply_chaos(year1_scores, personality_key=tl[-1]).get("events", [])

        # Re-generate with chaos injected (cache hit likely — same key)
        timelines_raw = generate_timelines(decision, context, chaos_events=chaos_events)
        timelines_raw.pop("_analysis", None)

        # 3. Separate metadata from narrative timelines
        causal_data     = {}
        interpretations = {}
        grounding_meta  = {}
        computed_meta   = {}
        timelines       = {}

        for name, tl in timelines_raw.items():
            if name.startswith("_"):
                continue
            causal_data[name]     = tl.pop("_causal", {})
            interpretations[name] = tl.pop("_interpretations", {})
            grounding_meta[name]  = tl.pop("_grounding", {})
            computed_meta[name]   = tl.pop("_computed", {})
            timelines[name]       = tl

        # 4. Batch synthesis: regret + letters + comparison (1 LLM call, cached)
        from quota_manager import get_quota_manager as _gqm
        import time as _time
        _qm = _gqm()
        print(f"[API] >>> batch_synthesis() starting | quota_mode={_qm.state['mode']} | calls_today={_qm.state['calls_today']}")
        # Brief pause to avoid TPM burst after timeline calls
        _time.sleep(2)
        synthesis  = batch_synthesis(
            {**timelines, **{k: timelines_raw[k] for k in timelines_raw if k in TIMELINE_KEYS}},
            decision, context,
        )
        regrets    = synthesis.get("regrets",    {})
        letters    = synthesis.get("letters",    {})
        comparison = synthesis.get("comparison", {})
        print(f"[API] <<< batch_synthesis() done | regrets_keys={list(regrets.keys())} | letters_keys={list(letters.keys())} | comparison_keys={list(comparison.keys())}")
        
        # 7. Save to database
        sim = Simulation(
            user_email=request.user_email,
            decision=decision,
            context=context,
            timelines=timelines,
            regrets=regrets,
            comparison=comparison,
            letters=letters,
        )
        db.add(sim)
        db.commit()
        db.refresh(sim)

        # 8. Schedule follow-up email if Celery and email available
        if CELERY_AVAILABLE and request.user_email:
            try:
                schedule_followup.delay(sim.id, request.user_email, decision)
            except Exception as e:
                print(f"[API] Failed to schedule follow-up: {e}")

        return SimulateResponse(
            simulation_id=sim.id,
            timelines=timelines,
            causal_data=causal_data,
            interpretations=interpretations,
            grounding=grounding_meta,
            computed=computed_meta,
            analysis=analysis,
            regrets=regrets,
            letters=letters,
            comparison=comparison,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    from quota_manager import get_quota_manager
    qm = get_quota_manager()
    stats = qm.stats()
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "llm_mode": stats["mode"],
        "calls_today": stats["calls_today"],
        "cache_enabled": True,
        "quota": stats,
    }


@app.post("/reset-quota")
async def reset_quota_endpoint():
    """Reset quota manager to full mode and clear call counters."""
    from quota_manager import get_quota_manager
    qm = get_quota_manager()
    qm.reset()
    return {"status": "ok", "quota": qm.stats()}


@app.post("/pivot", response_model=PivotResponse)
async def pivot(request: PivotRequest):
    """
    Branch a timeline from event_year onward with an alternative outcome.
    Years before the pivot are preserved; years from pivot onward are re-simulated.
    """
    try:
        new_timeline = generate_pivot_timeline(
            original_timeline=request.original_timeline,
            event_year=request.event_year,
            alternative_outcome=request.alternative_outcome,
            decision=request.decision,
            context=request.context,
        )

        # Strip internal keys for regret/letter agents
        narrative_only = {k: v for k, v in new_timeline.items() if not k.startswith("_")}
        causal = new_timeline.get("_causal", {})

        # Build a synthesis store specifically for this pivot branch
        from agents.synthesis import _fallback_regret, _fallback_letter
        pivot_tl_for_regret = {**narrative_only, "_causal": causal}
        regret = _fallback_regret("pivot", pivot_tl_for_regret)

        # Use LLM synthesis for pivot if quota allows
        from quota_manager import get_quota_manager
        from llm_client import call_llm
        import json as _json
        qm = get_quota_manager()
        if qm.should_use_llm("synthesis"):
            y10 = causal.get("Year10", {})
            pivot_prompt = f"""You are a decision simulation synthesis engine.

A person made this decision: "{request.decision}"
At Year {request.event_year}, something changed: "{request.alternative_outcome}"

Their Year-10 causal scores after this pivot:
{_json.dumps(y10, indent=2)}

Their Year-10 narrative: {new_timeline.get('Year10', '')}

Write:
1. A regret analysis for this pivot path (what did they give up by taking this branch?)
2. A 150-word letter from their Year-10 self reflecting on the pivot

Output ONLY valid JSON:
{{
  "regret": {{
    "lost_opportunity": "...",
    "missed_identity": "...",
    "emotional_cost": "..."
  }},
  "letter": "..."
}}"""
            try:
                raw = call_llm(pivot_prompt, temperature=0.75)
                qm.record_call()
                parsed = _json.loads(raw)
                regret = parsed.get("regret", regret)
                letter = parsed.get("letter", "")
                if not letter:
                    raise ValueError("empty letter")
            except Exception as exc:
                logger.warning("[Pivot] Synthesis LLM failed: %s — template fallback", exc)
                letter = _fallback_letter("pivot", pivot_tl_for_regret, regret)
        else:
            letter = _fallback_letter("pivot", pivot_tl_for_regret, regret)

        return PivotResponse(
            new_timeline=narrative_only,
            regret=regret,
            letter=letter,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/simulation/{simulation_id}")
async def get_simulation(simulation_id: int, db: Session = Depends(get_db)):
    """Retrieve a saved simulation by ID."""
    sim = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim.to_dict()


@app.post("/followup")
async def submit_followup(request: FollowUpRequest, db: Session = Depends(get_db)):
    """Submit a follow-up response for a simulation."""
    # Verify simulation exists
    sim = db.query(Simulation).filter(Simulation.id == request.simulation_id).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    followup = FollowUp(
        simulation_id=request.simulation_id,
        user_email=request.user_email or sim.user_email,
        actual_timeline=request.actual_timeline,
        feedback=request.feedback,
    )
    db.add(followup)
    db.commit()
    db.refresh(followup)
    
    return {"status": "success", "followup_id": followup.id}


@app.get("/followup/{simulation_id}")
async def get_followup_data(simulation_id: int, db: Session = Depends(get_db)):
    """Get data for the follow-up page."""
    sim = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    return {
        "simulation_id": sim.id,
        "decision": sim.decision,
        "timelines": list(sim.timelines.keys()),
        "created_at": sim.created_at.isoformat() if sim.created_at else None,
    }


# ── Feature 1: Personalised Career Score ─────────────────────────────────────

@app.post("/score")
async def personalised_score(request: ScoreRequest, db: Session = Depends(get_db)):
    """
    Compute a weighted score for each timeline based on user-defined value weights.
    Weights should sum to 1.0 (normalised automatically if not).
    """
    sim = db.query(Simulation).filter(Simulation.id == request.simulation_id).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    weights = request.weights
    total_w = sum(weights.values())
    if total_w <= 0:
        raise HTTPException(status_code=400, detail="Weights must sum to a positive number")
    # Normalise
    weights = {k: v / total_w for k, v in weights.items()}

    # Retrieve causal data from the simulation response stored in DB
    # We re-run grounding to get causal data (it's cached so free)
    try:
        timelines_raw = generate_timelines(sim.decision, sim.context)
        causal_data = {}
        for name, tl in timelines_raw.items():
            if name.startswith("_"):
                continue
            causal_data[name] = tl.get("_causal", {})
    except Exception:
        raise HTTPException(status_code=500, detail="Could not retrieve causal data")

    YEARS = ["Year1", "Year3", "Year5", "Year10"]
    YEAR_WEIGHTS = {"Year1": 0.1, "Year3": 0.2, "Year5": 0.3, "Year10": 0.4}

    scores = {}
    for tl_name, causal in causal_data.items():
        weighted_sum = 0.0
        for yr, yr_w in YEAR_WEIGHTS.items():
            yr_scores = causal.get(yr, {})
            yr_score = sum(
                yr_scores.get(node, 50) * node_w
                for node, node_w in weights.items()
                if node in yr_scores
            )
            weighted_sum += yr_score * yr_w
        scores[tl_name] = round(weighted_sum, 1)

    # Rank timelines
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    recommendation = ranked[0][0] if ranked else None

    return {
        "scores": scores,
        "ranked": [{"timeline": t, "score": s} for t, s in ranked],
        "recommendation": recommendation,
        "weights_used": weights,
    }


# ── Feature 3: Peer Comparison ────────────────────────────────────────────────

@app.get("/peer-comparison")
async def peer_comparison(
    decision_keywords: str = Query("", description="Comma-separated keywords from the decision"),
    db: Session = Depends(get_db),
):
    """
    Return anonymised peer outcome stats: what % of similar users ended up in each timeline.
    Matches on decision keywords and follow-up data.
    """
    followups = db.query(FollowUp).filter(FollowUp.actual_timeline.isnot(None)).all()

    if not followups:
        return {"message": "No follow-up data yet", "stats": {}, "total": 0}

    # Filter by keyword similarity if provided
    keywords = [k.strip().lower() for k in decision_keywords.split(",") if k.strip()]
    matched = []
    for fu in followups:
        sim = db.query(Simulation).filter(Simulation.id == fu.simulation_id).first()
        if sim:
            if not keywords or any(kw in sim.decision.lower() for kw in keywords):
                matched.append(fu)

    if not matched:
        matched = followups  # fall back to all data

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


# ── Feature 4: Counsellor Dashboard ──────────────────────────────────────────

@app.get("/counsellor/students")
async def counsellor_students(
    counsellor_email: str = Query(..., description="Counsellor's email address"),
    db: Session = Depends(get_db),
):
    """
    Return all simulations visible to a counsellor, with notes.
    In production this would be gated by auth; here we use email as a simple key.
    """
    # Get all simulations (counsellor sees all — add role-based auth in production)
    sims = db.query(Simulation).order_by(Simulation.created_at.desc()).limit(200).all()

    result = []
    for sim in sims:
        notes = db.query(CounsellorNote).filter(
            CounsellorNote.simulation_id == sim.id
        ).all()
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
    """Add a counsellor note to a simulation."""
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


# ── Feature 5: Compare Two Decisions ─────────────────────────────────────────

@app.post("/compare-two")
async def compare_two_decisions(request: CompareTwoRequest, db: Session = Depends(get_db)):
    """
    Run simulations for two different decisions and return side-by-side causal data.
    Both simulations are saved to the DB.
    """
    try:
        results = {}
        sim_ids = {}
        for label, decision in [("A", request.decision_a), ("B", request.decision_b)]:
            timelines_raw = generate_timelines(decision, request.context)
            analysis = timelines_raw.pop("_analysis", {})

            causal_data = {}
            interpretations = {}
            grounding_meta = {}
            computed_meta = {}
            timelines = {}

            for name, tl in timelines_raw.items():
                if name.startswith("_"):
                    continue
                causal_data[name] = tl.pop("_causal", {})
                interpretations[name] = tl.pop("_interpretations", {})
                grounding_meta[name] = tl.pop("_grounding", {})
                computed_meta[name] = tl.pop("_computed", {})
                timelines[name] = tl

            synthesis = batch_synthesis(
                {**timelines, **{k: timelines_raw[k] for k in timelines_raw if k in TIMELINE_KEYS}},
                decision, request.context,
            )

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
            sim_ids[label] = sim.id

        return {"decision_a": results["A"], "decision_b": results["B"]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 6: Live Job Market Integration ────────────────────────────────────

@app.get("/job-market")
async def job_market(
    role: str = Query("software engineer"),
    location: str = Query("Bangalore"),
    skills: str = Query("", description="Comma-separated skills to check demand for"),
):
    """
    Return live job market demand data for a role/location.
    Uses Adzuna API if key is set, otherwise returns enriched static data.
    """
    from data_grounding import detect_role, normalise_location, EMPLOYMENT_RATES, INDUSTRY_KEYWORDS
    from real_data_provider import get_ambitionbox_salary, get_worldbank_unemployment, get_worldbank_gdp_growth

    norm_location = normalise_location(location)
    norm_role = detect_role(role, {})

    # Live salary range
    salary_range = get_ambitionbox_salary(norm_role, norm_location)
    unemployment = get_worldbank_unemployment()
    gdp_growth = get_worldbank_gdp_growth()

    # Adzuna integration (optional)
    adzuna_data = None
    adzuna_app_id = os.environ.get("ADZUNA_APP_ID", "")
    adzuna_api_key = os.environ.get("ADZUNA_API_KEY", "")
    if adzuna_app_id and adzuna_api_key:
        try:
            import requests as req
            resp = req.get(
                f"https://api.adzuna.com/v1/api/jobs/in/search/1",
                params={
                    "app_id": adzuna_app_id,
                    "app_key": adzuna_api_key,
                    "what": role,
                    "where": location,
                    "results_per_page": 10,
                    "content-type": "application/json",
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                adzuna_data = {
                    "total_jobs": data.get("count", 0),
                    "mean_salary_inr": data.get("mean", None),
                    "source": "adzuna",
                }
        except Exception as e:
            pass  # degrade gracefully

    # Skill demand (static enrichment — extend with Adzuna/LinkedIn in production)
    skill_list = [s.strip() for s in skills.split(",") if s.strip()]
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
        "adzuna": adzuna_data,
        "skill_demand": skill_insights,
        "data_sources": {
            "salary": "AmbitionBox (live scrape)",
            "macro": "World Bank Open Data",
            "skills": "Static 2024 dataset (Adzuna/LinkedIn in production)",
        },
    }


# ── Feature 7: Verification Badge Registry ───────────────────────────────────

@app.get("/data-sources")
async def data_sources():
    """Return the registry of data sources used for grounding, for badge display."""
    return {
        "sources": [
            {
                "id": "ambitionbox",
                "label": "AmbitionBox",
                "description": "Live salary data scraped from AmbitionBox public pages",
                "url": "https://www.ambitionbox.com",
                "badge": "📊 AmbitionBox",
                "applies_to": ["income"],
            },
            {
                "id": "world_bank",
                "label": "World Bank Open Data",
                "description": "Unemployment %, CPI inflation %, GDP growth % for India",
                "url": "https://data.worldbank.org",
                "badge": "🌐 World Bank",
                "applies_to": ["opportunity", "stress"],
            },
            {
                "id": "india_happiness",
                "label": "World Happiness Report 2023",
                "description": "India happiness baseline (rank 126/137, score ~4.0/10)",
                "url": "https://worldhappiness.report",
                "badge": "😊 WHR 2023",
                "applies_to": ["happiness"],
            },
            {
                "id": "deloitte_survey",
                "label": "Deloitte India Millennial Survey 2023",
                "description": "82% of Indian urban professionals report high workplace stress",
                "url": "https://www2.deloitte.com/in/en/pages/about-deloitte/articles/millennialsurvey.html",
                "badge": "📋 Deloitte 2023",
                "applies_to": ["stress"],
            },
            {
                "id": "who_india",
                "label": "WHO India 2022",
                "description": "Sedentary lifestyle index for urban professionals",
                "url": "https://www.who.int/india",
                "badge": "🏥 WHO 2022",
                "applies_to": ["health"],
            },
            {
                "id": "india_happiness_report",
                "label": "India Happiness Report 2023",
                "description": "Social connectedness score for Indian urban professionals",
                "url": "https://www.happinessstudies.academy",
                "badge": "🤝 IHR 2023",
                "applies_to": ["relationships"],
            },
        ]
    }


# ── Feature 10: Longitudinal Outcome Library ─────────────────────────────────

@app.get("/outcomes")
async def outcome_library(
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """
    Public anonymised outcome library — aggregated from follow-up responses.
    Shows what actually happened vs what was predicted.
    """
    followups = (
        db.query(FollowUp)
        .filter(FollowUp.actual_timeline.isnot(None))
        .order_by(FollowUp.created_at.desc())
        .limit(limit)
        .all()
    )

    outcomes = []
    for fu in followups:
        sim = db.query(Simulation).filter(Simulation.id == fu.simulation_id).first()
        if not sim:
            continue
        # Anonymise: strip email, keep decision category + context shape
        ctx = dict(sim.context)
        ctx.pop("user_email", None)
        outcomes.append({
            "decision_preview": sim.decision[:80] + ("..." if len(sim.decision) > 80 else ""),
            "context": {
                "age": ctx.get("age"),
                "location": ctx.get("location"),
                "risk_tolerance": ctx.get("risk_tolerance"),
            },
            "chosen_timeline": fu.actual_timeline,
            "feedback_preview": (fu.feedback or "")[:120] + ("..." if fu.feedback and len(fu.feedback) > 120 else ""),
            "months_after": (
                int((fu.created_at - sim.created_at).days / 30)
                if fu.created_at and sim.created_at else None
            ),
        })

    # Aggregate stats
    total = db.query(FollowUp).filter(FollowUp.actual_timeline.isnot(None)).count()
    tl_counts: Dict[str, int] = {}
    for fu in db.query(FollowUp).filter(FollowUp.actual_timeline.isnot(None)).all():
        tl = fu.actual_timeline or "Unknown"
        tl_counts[tl] = tl_counts.get(tl, 0) + 1

    return {
        "outcomes": outcomes,
        "aggregate": {
            "total_followups": total,
            "timeline_distribution": tl_counts,
        },
    }


# --- Main ---

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

