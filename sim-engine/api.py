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