from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import os
import json

from input_validator import is_likely_meaningful, validate_context, describe_detection_failure
from models import (
    init_db, get_db, Simulation, FollowUp, CounsellorNote,
    EconomicSnapshot, SalaryData, JobMarketData, InflationData,
)
from sqlalchemy.orm import Session

class JsonFormatter(logging.Formatter):
    def format(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            msg = record.msg % record.args if isinstance(record.args, tuple) and record.args else (record.msg if hasattr(record, "msg") else str(record))
        payload = {
            "time": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": msg,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
root_logger = logging.getLogger()
if not root_logger.handlers:
    root_logger.addHandler(handler)
root_logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

logger = logging.getLogger(__name__)


def _dump_model(model):
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _persist_economic_snapshot(db: Session, snapshot, simulation_id: Optional[int] = None) -> Optional[EconomicSnapshot]:
    if snapshot is None:
        return None
    snapshot_data = _dump_model(snapshot)
    provider_status = {
        key: {
            "provider": value.get("provider"),
            "dataset": value.get("dataset"),
            "available": value.get("available"),
            "source_url": value.get("source_url"),
            "cache_hit": value.get("cache_hit"),
            "error": value.get("error"),
        }
        for key, value in snapshot_data.get("providers", {}).items()
    }
    row = EconomicSnapshot(
        simulation_id=simulation_id,
        role=snapshot.role,
        industry=snapshot.industry,
        location=snapshot.location,
        confidence=snapshot.confidence,
        gaps=snapshot_data.get("gaps", []),
        provider_status=provider_status,
        monitoring=snapshot_data.get("monitoring", {}),
        grounding=snapshot_data.get("grounding", {}),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    salary = snapshot_data.get("providers", {}).get("salary", {})
    salary_range = salary.get("data", {}).get("salary_range_lpa") or []
    db.add(SalaryData(
        economic_snapshot_id=row.id,
        role=snapshot.role,
        location=snapshot.location,
        source=salary.get("provider") or "unknown",
        min_lpa=salary_range[0] if len(salary_range) >= 1 else None,
        max_lpa=salary_range[1] if len(salary_range) >= 2 else None,
        source_url=salary.get("source_url"),
        available=bool(salary.get("available")),
        error=salary.get("error"),
    ))

    job_trends = snapshot_data.get("providers", {}).get("job_trends", {})
    db.add(JobMarketData(
        economic_snapshot_id=row.id,
        role=snapshot.role,
        location=snapshot.location,
        source=job_trends.get("provider") or "unknown",
        trend_payload=job_trends.get("data") or {},
        available=bool(job_trends.get("available")),
        error=job_trends.get("error"),
    ))

    worldbank = snapshot_data.get("providers", {}).get("worldbank", {})
    wb_values = worldbank.get("data", {}).get("values", {})
    wb_years = worldbank.get("data", {}).get("years", {})
    db.add(InflationData(
        economic_snapshot_id=row.id,
        country="IN",
        source=worldbank.get("provider") or "worldbank",
        inflation_pct=wb_values.get("inflation"),
        unemployment_pct=wb_values.get("unemployment"),
        gdp_growth_pct=wb_values.get("gdp_growth"),
        year=wb_years.get("inflation"),
        available=bool(worldbank.get("available")),
        error=worldbank.get("error"),
    ))
    db.commit()
    return row

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
    from quota_manager import get_quota_manager
    from llm_client import _provider_has_key
    qm = get_quota_manager()
    providers = {}
    for p in ["openai", "gemini", "groq", "openrouter", "anthropic"]:
        providers[p] = {
            "configured": _provider_has_key(p),
            "model": os.environ.get(f"{p.upper()}_MODEL", ""),
        }
    from services.decision_classifier import classify_decision
    return {
        "status": "healthy",
        "time": datetime.utcnow().isoformat(),
        "mode": qm.mode,
        "llm_mode": os.environ.get("QUOTA_MODE", "deterministic"),
        "providers": providers,
        "quota": qm.stats(),
        "simulations": {
            "deterministic_formulas": True,
            "monte_carlo": True,
            "real_time_data": True,
        },
    }


@app.get("/data-health")
async def data_health():
    from services.common import cache
    from services.sync_data import _DATA_SOURCES
    now = datetime.utcnow().isoformat()
    data_sources = dict(_DATA_SOURCES)
    available_count = sum(1 for v in data_sources.values() if v.get("available"))
    total_count = len(data_sources)
    return {
        "status": "ok",
        "time": now,
        "total_sources": total_count,
        "available_sources": available_count,
        "availability_pct": round(available_count / max(total_count, 1) * 100, 1),
        "sources": data_sources,
    }


@app.get("/debug/system-health")
async def system_health():
    errors = []

    # data_grounding loaded
    data_grounding_loaded = False
    try:
        from data_grounding import (get_grounding_data, build_score_anchors, score_to_lpa, compute_core_variables)
        data_grounding_loaded = True
    except ImportError as e:
        errors.append({"component": "data_grounding", "status": "import_failed", "detail": str(e)})

    # salary_provider
    salary_provider_status = "unknown"
    try:
        from services.ambitionbox import fetch_salary
        adzuna_id = bool(os.environ.get("ADZUNA_APP_ID"))
        adzuna_key = bool(os.environ.get("ADZUNA_API_KEY"))
        rapid_key = bool(os.environ.get("RAPIDAPI_KEY"))
        if adzuna_id and adzuna_key:
            salary_provider_status = "healthy"
        elif rapid_key:
            salary_provider_status = "degraded (JSearch only)"
        else:
            salary_provider_status = "unconfigured"
            errors.append({"component": "salary_provider", "status": "no_api_keys", "detail": "ADZUNA_APP_ID/ADZUNA_API_KEY or RAPIDAPI_KEY required"})
    except ImportError as e:
        salary_provider_status = "import_failed"
        errors.append({"component": "salary_provider", "status": "import_failed", "detail": str(e)})

    # routing_engine (decision_classifier)
    routing_engine_status = "healthy"
    try:
        from services.decision_classifier import classify_decision
        test = classify_decision("Should I take NEET or JEE", {"location": "India"})
        if test.category.value != "educational":
            errors.append({"component": "routing_engine", "status": "incorrect_routing", "detail": f"Expected educational, got {test.category.value}"})
            routing_engine_status = "degraded"
    except ImportError as e:
        errors.append({"component": "routing_engine", "status": "import_failed", "detail": str(e)})
        routing_engine_status = "import_failed"
    except Exception as e:
        errors.append({"component": "routing_engine", "status": "runtime_error", "detail": str(e)})
        routing_engine_status = "error"

    # timeline_engine
    timeline_engine_status = "healthy"
    try:
        from agents.timeline import _get_anchors, _score_to_lpa_safe
        anchors = _get_anchors("Test decision", {"location": "India"})
        lpa = _score_to_lpa_safe(50, anchors)
        if lpa is not None and (lpa < 0 or lpa > 100):
            errors.append({"component": "timeline_engine", "status": "unexpected_value", "detail": f"lpa={lpa}"})
    except ImportError as e:
        errors.append({"component": "timeline_engine", "status": "import_failed", "detail": str(e)})
        timeline_engine_status = "import_failed"
    except Exception as e:
        errors.append({"component": "timeline_engine", "status": "runtime_error", "detail": str(e)})
        timeline_engine_status = "error"

    # worldbank_provider
    worldbank_provider_status = "healthy"
    try:
        from services.worldbank import fetch_worldbank
    except ImportError as e:
        errors.append({"component": "worldbank_provider", "status": "import_failed", "detail": str(e)})
        worldbank_provider_status = "import_failed"

    # aggregator
    aggregator_status = "healthy"
    try:
        from services.aggregator import collect_economic_snapshot
    except ImportError as e:
        errors.append({"component": "aggregator", "status": "import_failed", "detail": str(e)})
        aggregator_status = "import_failed"

    return {
        "data_grounding_loaded": data_grounding_loaded,
        "salary_provider": salary_provider_status,
        "routing_engine": routing_engine_status,
        "timeline_engine": timeline_engine_status,
        "worldbank_provider": worldbank_provider_status,
        "aggregator": aggregator_status,
        "errors": errors,
        "time": datetime.utcnow().isoformat(),
    }


@app.get("/sources-status")
async def sources_status():
    statuses = {
        "worldbank": {},
        "ambitionbox_salary": {},
        "numbeo": {},
        "adzuna": {},
        "fred": {},
        "imf": {},
        "india_gov": {},
    }
    from services.common import cache
    services_map = {
        "worldbank": ("services.worldbank", "fetch_worldbank", "https://api.worldbank.org/v2/country/IN/indicator/"),
        "ambitionbox_salary": ("services.ambitionbox", "fetch_salary", "https://www.ambitionbox.com/profile/"),
        "numbeo": ("services.numbeo", "fetch_cost_of_living", "https://www.numbeo.com/api/city_prices"),
        "adzuna": ("services.job_market", "fetch_adzuna_jobs", "https://api.adzuna.com/v1/api/jobs"),
        "fred": ("services.fred", "fetch_industry_data", "https://api.stlouisfed.org/fred/series"),
        "imf": ("services.imf", "fetch_imf", "https://www.imf.org/external/datamapper/api/v1/"),
        "india_gov": ("services.india_gov", "fetch_india_gov_stats", "https://api.data.gov.in/resource/"),
    }
    for name, (module_name, func_name, url) in services_map.items():
        module = None
        try:
            import importlib
            module = importlib.import_module(module_name)
        except Exception:
            pass
        if module:
            func = getattr(module, func_name, None)
            statuses[name] = {
                "module_loaded": True,
                "function_found": func is not None,
                "url": url,
            }
            if name == "adzuna" or name == "ambitionbox_salary":
                statuses[name]["api_key_configured"] = bool(os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_API_KEY"))
            elif name == "numbeo":
                statuses[name]["api_key_configured"] = bool(os.environ.get("NUMBEO_API_KEY"))
            elif name == "fred":
                statuses[name]["api_key_configured"] = bool(os.environ.get("FRED_API_KEY"))
            else:
                statuses[name]["api_key_configured"] = True
        else:
            statuses[name] = {
                "module_loaded": False,
                "function_found": False,
                "url": url,
                "api_key_configured": False,
            }
    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat(),
        "sources": statuses,
    }


# =========================
# MODELS
# =========================

class SimulateRequest(BaseModel):
    decision: str
    context: Dict[str, Any]
    user_email: Optional[str] = None
    deterministic: bool = True
    llm_format: bool = False
    collect_economic_data: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "decision": "Should I study CSE or AIML at VIT?",
                "context": {"age": 18, "location": "Bangalore", "risk_tolerance": "medium"},
                "deterministic": True,
                "llm_format": False,
            }
        }


# =========================
# MAIN ENDPOINT
# =========================

@app.post("/simulate")
async def simulate(request: SimulateRequest, db: Session = Depends(get_db)):
    try:
        decision = request.decision
        context = request.context

        # ── Log the incoming request ─────────────────────────────────────────
        logger.info("=" * 60)
        logger.info("SIMULATE REQUEST")
        logger.info("Decision: %s", decision)
        logger.info("Context: %s", json.dumps(context, default=str))
        logger.info("User email: %s", request.user_email)
        logger.info("Mode: deterministic=%s llm_format=%s", request.deterministic, request.llm_format)
        logger.info("=" * 60)

        # ── Validate input quality ────────────────────────────────────────────
        data_warnings = []
        valid, msg = is_likely_meaningful(decision)
        if not valid:
            raise ValueError(msg)
        context_warnings = validate_context(context)
        if context_warnings:
            data_warnings.extend(context_warnings)
        detection_warnings = describe_detection_failure(decision, context)
        data_warnings.extend(detection_warnings)

        from decision_parser import parse_decision
        parsed = parse_decision(decision)
        logger.info("Parsed decision: options=%s type=%s confidence=%d",
                     parsed.options, parsed.decision_type, parsed.confidence)

        if parsed.confidence < 50:
            msg = f"Unable to confidently parse this decision (confidence: {parsed.confidence}%). The simulation may not fully reflect your question."
            data_warnings.append(msg)
            logger.warning("Low decision parsing confidence (%d%%) — will flag in response",
                           parsed.confidence)

        # ── DETERMINISTIC PIPELINE (default, 0 LLM calls) ───────────────────
        if request.deterministic:
            from simulation_engine import run_simulation
            from agents.chaos import apply_chaos

            # Optional: collect economic data for grounding enrichment
            economic_snapshot = None
            macro_relevant = {"career", "business", "financial", "relocation"}
            if request.collect_economic_data and parsed.decision_type in macro_relevant:
                try:
                    from services.aggregator import collect_economic_snapshot
                    economic_snapshot = await collect_economic_snapshot(decision, context)
                    snapshot_payload = _dump_model(economic_snapshot)
                    econ_context = {
                        "_economic_snapshot": {
                            "confidence": economic_snapshot.confidence,
                            "messages": economic_snapshot.user_messages(),
                            "monitoring": snapshot_payload.get("monitoring", {}),
                            "grounding": snapshot_payload.get("grounding", {}),
                        },
                    }
                    context = {**context, **econ_context}
                except Exception as exc:
                    logger.warning("[Simulate] Economic data collection failed: %s — continuing without", exc)

            # Chaos events (deterministic)
            chaos_events = {}
            for tl in ["Timeline A", "Timeline B", "Timeline C"]:
                try:
                    chaos_events[tl] = apply_chaos({}, personality_key=tl[-1]).get("events", [])
                except Exception:
                    chaos_events[tl] = []

            # Define the optional LLM formatter
            def _llm_formatter(synthesis, timelines, decision, context):
                if not request.llm_format:
                    return None
                from llm_client import call_llm
                from quota_manager import get_quota_manager
                qm = get_quota_manager()
                if not qm.should_use_llm("synthesis"):
                    return None
                summary = {
                    "winner": "Timeline B",
                    "salary_diff": 12,
                    "risk_diff": 4,
                }
                prompt = (
                    f"Explain these career simulation results naturally in 2-3 sentences.\n\n"
                    f"Decision: {decision}\n"
                    f"Regrets: {json.dumps(synthesis.get('regrets', {}), indent=2)[:500]}\n"
                    f"Comparison: {json.dumps(synthesis.get('comparison', {}), indent=2)[:500]}\n\n"
                    f"Output a short paragraph explaining the key trade-offs."
                )
                try:
                    raw = call_llm(prompt, temperature=0.5)
                    qm.record_call()
                    return {"llm_explanation": raw}
                except Exception as exc:
                    logger.warning("[Simulate] LLM formatter failed: %s", exc)
                    return None

            result = run_simulation(
                decision=decision,
                context=context,
                chaos_events=chaos_events,
                llm_format=request.llm_format,
                llm_formatter=_llm_formatter if request.llm_format else None,
            )

            # Merge economic data if available
            if economic_snapshot:
                result["data_confidence"] = economic_snapshot.confidence
                result["data_confidence_explanation"] = economic_snapshot.confidence_explanation
                result["data_warnings"] = economic_snapshot.user_messages() + data_warnings
                if "_economic_snapshot" in context:
                    result["data_monitoring"] = context["_economic_snapshot"].get("monitoring", {})
                economic_row = _persist_economic_snapshot(db, economic_snapshot)
                result["economic_snapshot_id"] = economic_row.id
            else:
                result["data_warnings"] = data_warnings
                economic_row = None

            # Persist
            sim = Simulation(
                user_email=request.user_email,
                decision=decision,
                context=context,
                timelines=result.get("timelines", {}),
                regrets=result.get("regrets", {}),
                comparison=result.get("comparison", {}),
                letters=result.get("letters", {}),
            )
            db.add(sim)
            db.commit()
            db.refresh(sim)
            result["simulation_id"] = sim.id
            if economic_row:
                economic_row.simulation_id = sim.id
                db.commit()

            return result

        # ── LEGACY LLM PIPELINE (opt-in, backward compatible) ───────────────
        economic_snapshot = None
        enriched_context = dict(context)
        if parsed.decision_type == "career":
            from services.aggregator import collect_economic_snapshot

            economic_snapshot = await collect_economic_snapshot(decision, context)
            snapshot_payload = _dump_model(economic_snapshot)
            if "_economic_snapshot" in context:
                data_warnings.append("Context field '_economic_snapshot' is reserved and will be overwritten.")
            enriched_context = {
                **{k: v for k, v in context.items() if not k.startswith("_")},
                "_economic_snapshot": {
                    "confidence": economic_snapshot.confidence,
                    "messages": economic_snapshot.user_messages(),
                    "monitoring": snapshot_payload.get("monitoring", {}),
                    "grounding": snapshot_payload.get("grounding", {}),
                },
            }

        from agents.timeline import generate_timelines, TIMELINE_KEYS
        from agents.chaos import apply_chaos
        from agents.synthesis import batch_synthesis

        timelines_raw = generate_timelines(decision, enriched_context)
        analysis = timelines_raw.pop("_analysis", {})

        chaos_events = {}
        for tl in TIMELINE_KEYS:
            year1 = timelines_raw.get(tl, {}).get("_causal", {}).get("Year1", {})
            chaos_events[tl] = apply_chaos(year1, personality_key=tl[-1]).get("events", [])

        timelines_raw = generate_timelines(decision, enriched_context, chaos_events=chaos_events)

        timelines = {}
        causal_data = {}
        interpretations = {}
        grounding_meta = {}
        computed_meta = {}
        for name, tl in timelines_raw.items():
            if not name.startswith("_"):
                timelines[name] = tl
                causal_data[name] = tl.get("_causal", {})
                interpretations[name] = tl.get("_interpretations", {})
                grounding_meta[name] = tl.get("_grounding", {})
                computed_meta[name] = tl.get("_computed", {})

        archetype_labels = {
            "Timeline A": "The Settler",
            "Timeline B": "The Climber",
            "Timeline C": "The Gambler",
        }

        synthesis = batch_synthesis(timelines, decision, enriched_context)

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
        economic_row = None
        if economic_snapshot:
            economic_row = _persist_economic_snapshot(db, economic_snapshot, simulation_id=sim.id)

        if economic_snapshot:
            data_conf = economic_snapshot.confidence
            data_conf_explanation = economic_snapshot.confidence_explanation
            data_warnings_final = economic_snapshot.user_messages() + data_warnings
            data_monitoring = snapshot_payload.get("monitoring", {})
        else:
            data_conf = None
            data_conf_explanation = []
            data_warnings_final = data_warnings
            data_monitoring = {}

        return {
            "simulation_id": sim.id,
            "economic_snapshot_id": economic_row.id if economic_row else None,
            "archetype_labels": archetype_labels,
            "timelines": timelines,
            "causal_data": causal_data,
            "interpretations": interpretations,
            "grounding": grounding_meta,
            "computed": computed_meta,
            "data_confidence": data_conf,
            "data_confidence_explanation": data_conf_explanation,
            "data_warnings": data_warnings_final,
            "data_monitoring": data_monitoring,
            "analysis": analysis,
            "regrets": synthesis.get("regrets", {}),
            "letters": synthesis.get("letters", {}),
            "comparison": synthesis.get("comparison", {}),
            "decision_parsing": {
                "options": parsed.options,
                "type": parsed.decision_type,
                "confidence": parsed.confidence,
                "institution": parsed.institution,
                "year": parsed.year,
            },
        }

    except Exception as e:
        logger.exception("[Simulate] Unhandled error in /simulate")
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# V2 PIPELINE ENDPOINT
# =========================

@app.post("/simulate/v2")
async def simulate_v2(request: SimulateRequest):
    """Decision-type-aware pipeline. No global economic snapshot."""
    try:
        from simulation_pipeline import run_pipeline
        result = run_pipeline(
            decision=request.decision,
            context=request.context,
        )
        result["_meta"] = {
            "pipeline": "v2",
            "deterministic": True,
            "llm_calls": 0,
        }
        return result
    except Exception as e:
        logger.exception("[SimulateV2] Pipeline error")
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
        valid, msg = is_likely_meaningful(request.decision)
        if not valid:
            raise ValueError(msg)
        valid, msg = is_likely_meaningful(request.alternative_outcome)
        if not valid:
            raise ValueError(f"alternative_outcome: {msg}")
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

    causal_data = {
        name: tl.get("_causal", {})
        for name, tl in (sim.timelines or {}).items()
        if not name.startswith("_")
    }
    if not causal_data:
        raise HTTPException(status_code=500, detail="Stored causal data unavailable")

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
        for label, decision in [("A", request.decision_a), ("B", request.decision_b)]:
            valid, msg = is_likely_meaningful(decision)
            if not valid:
                raise ValueError(f"Decision {label}: {msg}")

        from agents.timeline import generate_timelines, TIMELINE_KEYS
        from agents.synthesis import batch_synthesis
        from decision_parser import parse_decision
        from services.aggregator import collect_economic_snapshot

        results = {}
        for label, decision in [("A", request.decision_a), ("B", request.decision_b)]:
            parsed = parse_decision(decision)
            economic_snapshot = None
            enriched_context = dict(request.context)
            if parsed.decision_type == "career":
                economic_snapshot = await collect_economic_snapshot(decision, request.context)
                snapshot_payload = _dump_model(economic_snapshot)
                enriched_context = {
                    **{k: v for k, v in request.context.items() if not k.startswith("_")},
                    "_economic_snapshot": {
                        "confidence": economic_snapshot.confidence,
                        "messages": economic_snapshot.user_messages(),
                        "monitoring": snapshot_payload.get("monitoring", {}),
                        "grounding": snapshot_payload.get("grounding", {}),
                    },
                }
            timelines_raw = generate_timelines(decision, enriched_context)
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

            synthesis = batch_synthesis(timelines, decision, enriched_context)

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
            economic_row = None
            if economic_snapshot:
                economic_row = _persist_economic_snapshot(db, economic_snapshot, simulation_id=sim.id)

            if economic_snapshot:
                data_conf = economic_snapshot.confidence
                data_conf_explanation = economic_snapshot.confidence_explanation
                data_warnings_final = economic_snapshot.user_messages()
                data_monitoring = snapshot_payload.get("monitoring", {})
            else:
                data_conf = None
                data_conf_explanation = []
                data_warnings_final = []
                data_monitoring = {}

            results[label] = {
                "simulation_id": sim.id,
                "economic_snapshot_id": economic_row.id if economic_row else None,
                "decision": decision,
                "timelines": timelines,
                "causal_data": causal_data,
                "interpretations": interpretations,
                "grounding": grounding_meta,
                "computed": computed_meta,
                "data_confidence": data_conf,
                "data_confidence_explanation": data_conf_explanation,
                "data_warnings": data_warnings_final,
                "data_monitoring": data_monitoring,
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
    role: str = Query(None),
    location: str = Query("Bangalore"),
    skills: str = Query(""),
):
    import traceback
    logger.warning("[JOB-MARKET] CALLED role=%s location=%s skills=%s stack=%s",
                   role, location, skills, "".join(traceback.format_stack()[:-1]))

    if not role:
        return {
            "role": None,
            "location": location,
            "salary_range_lpa": None,
            "unemployment_pct": None,
            "gdp_growth_pct": None,
            "skill_demand": {},
            "data_sources": {"salary": "none", "macro": "none"},
            "note": "No role provided — job market data requires a specific role.",
        }

    norm_role = role
    norm_location = location
    salary_range = [8, 25]
    unemployment = 7.5
    gdp_growth = 6.5
    salary_source = "static_fallback"
    macro_source = "world_bank_estimate"

    try:
        from data_grounding import detect_role, normalise_location
        from real_data_provider import get_ambitionbox_salary, get_worldbank_unemployment, get_worldbank_gdp_growth
        norm_location = normalise_location(location)
        norm_role = detect_role(role, {})

        ambition_salary = get_ambitionbox_salary(norm_role, norm_location)
        if ambition_salary:
            salary_range = ambition_salary
            salary_source = "ambitionbox_com"

        wb_unemployment = get_worldbank_unemployment()
        if wb_unemployment is not None:
            unemployment = wb_unemployment
            macro_source = "world_bank"

        wb_gdp = get_worldbank_gdp_growth()
        if wb_gdp is not None:
            gdp_growth = wb_gdp
            if macro_source != "world_bank":
                macro_source = "world_bank"
    except Exception:
        pass

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
        "data_sources": {
            "salary": salary_source,
            "macro": macro_source,
        },
        "adzuna": None,
    }


# =========================
# ECONOMIC RESEARCH
# =========================

class EconomicResearchRequest(BaseModel):
    decision: str
    context: Dict[str, Any]
    country: str = "IN"

@app.post("/economic-research")
async def economic_research(request: EconomicResearchRequest):
    """
    Run the Real-Time Economic Research Agent.
    Returns salary_growth, job_market, inflation, cost_of_living, future_trends
    with explicit missing-data tracking and a confidence score.
    """
    try:
        valid, msg = is_likely_meaningful(request.decision)
        if not valid:
            raise ValueError(msg)
        from agents.economic_research import collect_economic_research
        report = await collect_economic_research(
            request.decision,
            request.context,
            country=request.country,
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# =========================
# OPTION COMPARISON (Deterministic)
# =========================

class CompareOptionsRequest(BaseModel):
    decision: str
    context: Dict[str, Any] = {}
    user_email: Optional[str] = None

@app.post("/simulate-compare")
async def simulate_compare(request: CompareOptionsRequest):
    """
    Direct option-to-option comparison. 0 LLM calls.

    Parses "CSE or AIML at VIT?" into options=["CSE","AIML"],
    looks up career profiles for each, computes scores, and returns
    a winner with dimension-by-dimension comparison.
    """
    try:
        from simulation_engine import make_option_comparison
        from decision_parser import parse_decision

        parsed = parse_decision(request.decision)
        result = make_option_comparison(
            decision=request.decision,
            context=request.context,
            parsed=parsed,
        )
        result["decision_parsing"] = {
            "options": parsed.options,
            "type": parsed.decision_type,
            "confidence": parsed.confidence,
            "institution": parsed.institution,
            "year": parsed.year,
        }
        return result
    except Exception as e:
        logger.error("[CompareOptions] Failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# LANGGRAPH V2 SIMULATION
# =========================

class SimulateV2Request(BaseModel):
    decision: str
    context: dict
    economic_override: Optional[dict] = None
    enable_monte_carlo: bool = False
    monte_carlo_iterations: int = 100


@app.post("/simulate-v2")
async def simulate_v2(request: SimulateV2Request):
    try:
        valid, msg = is_likely_meaningful(request.decision)
        if not valid:
            raise HTTPException(status_code=400, detail=f"Invalid decision: {msg}")

        from graph.workflows.simulation import run_simulation
        from graph.workflows.monte_carlo import run_monte_carlo

        result = run_simulation(
            decision=request.decision,
            context=request.context,
            economic_override=request.economic_override,
        )

        if request.enable_monte_carlo:
            mc = run_monte_carlo(
                decision=request.decision,
                context=request.context,
                iterations=min(request.monte_carlo_iterations, 1000),
            )
            result["monte_carlo"] = mc

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[V2] Simulation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# FUTURE SELF CHAT
# =========================

class FutureChatRequest(BaseModel):
    timeline_label: str
    question: str
    future_self_persona: dict
    timeline_data: dict
    conversation_history: Optional[list] = None


@app.post("/future-chat")
async def future_chat(request: FutureChatRequest):
    try:
        from graph.workflows.future_chat import run_future_chat

        response = run_future_chat(
            timeline_label=request.timeline_label,
            user_question=request.question,
            future_self_persona=request.future_self_persona,
            timeline_data=request.timeline_data,
            conversation_history=request.conversation_history,
        )
        return {"response": response, "timeline": request.timeline_label}
    except Exception as e:
        logger.error("[FutureChat] Failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# MONTE CARLO
# =========================

class MonteCarloRequest(BaseModel):
    decision: str
    context: dict
    iterations: int = 100


@app.post("/monte-carlo")
async def monte_carlo_endpoint(request: MonteCarloRequest):
    try:
        from graph.workflows.monte_carlo import run_monte_carlo

        iterations = min(max(request.iterations, 10), 1000)
        result = run_monte_carlo(
            decision=request.decision,
            context=request.context,
            iterations=iterations,
        )
        return result
    except Exception as e:
        logger.error("[MonteCarlo] Failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# MEMORY
# =========================

class MemoryQueryRequest(BaseModel):
    query: str
    n_results: int = 5
    filter_type: Optional[str] = None


@app.post("/memory/query")
async def query_memory(request: MemoryQueryRequest):
    try:
        from memory.chroma_store import get_memory_store
        store = get_memory_store()
        results = store.query(
            query_text=request.query,
            n_results=min(request.n_results, 20),
            filter_type=request.filter_type,
        )
        return {"results": results}
    except Exception as e:
        logger.error("[Memory] Query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/store")
async def store_in_memory(
    user_id: str,
    decision: str,
    simulation_id: str,
    result: dict,
):
    try:
        from memory.chroma_store import get_memory_store
        store = get_memory_store()
        store.store_simulation(
            user_id=user_id,
            decision=decision,
            simulation_id=simulation_id,
            result=result,
        )
        return {"status": "stored"}
    except Exception as e:
        logger.error("[Memory] Store failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# =========================
# OBSERVABILITY
# =========================

@app.on_event("startup")
async def startup_observability():
    sentry_dsn = os.environ.get("SENTRY_DSN")
    if sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=sentry_dsn,
                traces_sample_rate=0.1,
                environment=os.environ.get("ENVIRONMENT", "development"),
            )
            logger.info("[Sentry] Initialized")
        except Exception as e:
            logger.warning("[Sentry] Failed to initialize: %s", e)

    langsmith_api = os.environ.get("LANGSMITH_API_KEY")
    if langsmith_api:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = "futureweave"
        logger.info("[LangSmith] Tracing enabled")


# =========================
# V2 API ROUTER
# =========================
from api_v2 import router as v2_router
app.include_router(v2_router)
