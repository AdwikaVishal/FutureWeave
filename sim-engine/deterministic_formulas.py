"""
Deterministic Formulas Engine — the mathematical heart of FutureWeave.

Every formula takes (profile, context, economic_data, year_index) and returns
a computed score.  Pure math — zero LLM calls.

Formulas are scaled to 0–100 and designed to produce realistic trajectories
across Year1 → Year3 → Year5 → Year7 → Year10.
"""

import math
import logging
from typing import Any

logger = logging.getLogger(__name__)


def safe_lower(value):
    if value is None:
        return ""
    return str(value).lower()


def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


_YEARS = ["Year1", "Year3", "Year5", "Year7", "Year10"]
_YEAR_INDICES = {
    "Year1": 0, "Year2": 1, "Year3": 2,
    "Year5": 4, "Year7": 6, "Year10": 9,
    "year1": 0, "year2": 1, "year3": 2,
    "year5": 4, "year7": 6, "year10": 9,
}


# ── Helpers ───────────────────────────────────────────────────────────────

def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


def _growth_curve(base: float, rate: float, t: float, cap: float = 100.0) -> float:
    """Logistic growth: base approaches cap at given rate over time t."""
    return _clamp(base + (cap - base) * (1 - math.exp(-rate * t)))


def _decay_curve(start: float, rate: float, t: float, floor: float = 0.0) -> float:
    """Exponential decay from start toward floor."""
    return _clamp(start - (start - floor) * (1 - math.exp(-rate * t)))


def _year_multiplier(year_key: str, base: float = 1.0) -> float:
    """Time multiplier for compound effects."""
    idx = _YEAR_INDICES.get(year_key, 0)
    return base * (1 + idx * 0.3)


# ── Career Formulas ───────────────────────────────────────────────────────

def compute_skill_growth(
    profile: dict,
    context: dict,
    economic: dict,
    year_key: str,
) -> dict:
    """Skill growth follows logistic curve modulated by industry demand."""
    idx = _YEAR_INDICES.get(year_key, 0)
    t = idx + 1  # 1, 2, 3, 4, 5

    industry_demand = (economic.get("industry_health") or 78) / 100.0
    automation_risk = (economic.get("automation_risk") or 15) / 100.0
    learning_ability = 1.0 + (0.2 if context.get("skills") else 0.0)

    base = 30.0
    rate = 0.25 * industry_demand * learning_ability
    cap = 95.0 * (1 - automation_risk * 0.3)

    score = _growth_curve(base, rate, t, cap)
    narratives = [
        "Building foundational skills in your role.",
        "Core competencies established, starting to specialize.",
        "Deep expertise in chosen domain.",
        "Strategic skills developing alongside technical depth.",
        "Mastery level — mentoring others and setting direction.",
    ]
    return {
        "year": year_key,
        "score": round(score, 1),
        "narrative": narratives[min(idx, 4)],
    }


def compute_employability(
    profile: dict,
    context: dict,
    economic: dict,
    year_key: str,
) -> dict:
    """Employability based on industry health, location, and automation risk."""
    industry_health = (economic.get("industry_health") or 78) / 100.0
    unemp = economic.get("unemployment_rate") or 4.22
    automation_risk = (economic.get("automation_risk") or 15) / 100.0
    location = context.get("location", "India")

    location_bonus = 1.1 if location in ("Bangalore", "Mumbai", "Hyderabad", "Delhi") else 1.0
    seniority_curve = _growth_curve(55.0, 0.15, _YEAR_INDICES.get(year_key, 0) + 1, 90.0)
    employability = seniority_curve * industry_health * location_bonus
    employability *= (1 - automation_risk * 0.4)

    narratives = [
        "Entry-level market demand is strong for your field.",
        "Mid-level professionals with your skillset are in demand.",
        "Senior-level positioning with multiple options available.",
        "Leadership roles narrower but higher value.",
        "Executive market is relationship-driven.",
    ]
    idx = _YEAR_INDICES.get(year_key, 0)
    return {
        "year": year_key,
        "score": round(_clamp(employability), 1),
        "narrative": narratives[min(idx, 4)],
    }


def compute_leadership(
    profile: dict,
    context: dict,
    economic: dict,
    year_key: str,
) -> dict:
    """Leadership score based on experience, industry health, and risk tolerance."""
    idx = _YEAR_INDICES.get(year_key, 0)
    t = idx + 1

    industry_demand = (economic.get("industry_health") or 78) / 100.0
    risk = context.get("risk_tolerance", "medium")
    pace = {"low": 0.8, "medium": 1.0, "high": 1.2}.get(risk, 1.0)

    base = 25.0
    rate = 0.2 * industry_demand * pace
    cap = 92.0

    score = _growth_curve(base, rate, t, cap)
    narratives = [
        "Early career — learning team collaboration and basic project ownership.",
        "Taking on mentorship of junior team members.",
        "Leading small teams or key initiatives independently.",
        "Strategic leadership — influencing org-level decisions.",
        "Executive presence — shaping vision, culture, and direction.",
    ]
    return {
        "year": year_key,
        "score": round(score, 1),
        "narrative": narratives[min(idx, 4)],
    }


def compute_promotion_timeline(
    profile: dict,
    context: dict,
    economic: dict,
) -> list:
    """Generate promotion timeline based on growth rate and risk tolerance."""
    risk = context.get("risk_tolerance", "medium")
    pace = {"low": 0.8, "medium": 1.0, "high": 1.2}.get(risk, 1.0)
    industry_demand = (economic.get("industry_health") or 78) / 100.0
    automation_risk = (economic.get("automation_risk") or 15) / 100.0
    inv_return = (economic.get("interest_rate") or 6.5) / 100.0
    disposable_income = economic.get("disposable_income") or 35000
    savings_rate_val = context.get("savings_rate") or economic.get("savings_rate") or 44.3
    monthly_saved = disposable_income * (savings_rate_val / 100.0)

    milestones = [
        {"year": "Year1", "title": "Associate", "salary_hike": "0-8%"},
        {"year": "Year3", "title": "Senior Associate", "salary_hike": "15-25%"},
        {"year": "Year5", "title": "Manager", "salary_hike": "30-50%"},
        {"year": "Year7", "title": "Senior Manager", "salary_hike": "50-80%"},
        {"year": "Year10", "title": "Director", "salary_hike": "80-120%"},
    ]
    return milestones


def compute_net_worth(
    profile: dict,
    context: dict,
    economic: dict,
    year_key: str,
    salary_lpa: float = 9.5,
    disposable: float = 35000,
    savings_rate: float = 44.3,
) -> dict:
    """Net worth accumulation — savings compound with investment growth."""
    idx = _YEAR_INDICES.get(year_key, 0)
    t = idx + 1
    industry_demand = (economic.get("industry_health") or 78) / 100.0
    inv_return = (economic.get("interest_rate") or 6.5) / 100.0
    monthly_saved = disposable * ((savings_rate or 44.3) / 100.0)
    months = (t * 2) * 12

    accumulated = 0.0
    for m in range(int(months)):
        accumulated += monthly_saved
        accumulated *= (1 + inv_return / 12)

    risk = context.get("risk_tolerance", "medium")
    risk_mult = {"low": 0.9, "medium": 1.0, "high": 1.2}.get(risk, 1.0)
    accumulated *= risk_mult

    narratives = [
        f"Building emergency fund from ₹{salary_lpa} LPA salary — early stage accumulation.",
        "Steady accumulation with disciplined savings rate.",
        "Savings compounding meaningfully with career growth.",
        "Investment returns contributing significantly to wealth growth.",
        "Decade of disciplined saving plus investment growth building substantial corpus.",
    ]

    return {
        "year": year_key,
        "amount": round(accumulated),
        "narrative": narratives[min(idx, 4)],
    }


def compute_financial_risk(
    profile: dict,
    context: dict,
    economic: dict,
    year_key: str,
) -> dict:
    """Financial risk based on debt, unemployment, and economic factors."""
    unemp = economic.get("unemployment_rate") or 4.22
    cpi = economic.get("inflation_cpi") or 4.95
    fin_cond = context.get("financial_condition", "stable")

    base_risk = 20.0
    unemp_risk = max(0, (unemp - 4.0) * 5)
    inflation_risk = max(0, (cpi - 4.0) * 3)
    condition_risk = {"stable": 0, "tight": 15, "struggling": 30, "in_debt": 45}.get(fin_cond, 10)

    total_risk = base_risk + unemp_risk + inflation_risk + condition_risk
    idx = _YEAR_INDICES.get(year_key, 0)
    # Risk decreases over time as career stabilizes
    total_risk *= (1 - idx * 0.03)
    total_risk = _clamp(total_risk, 5, 85)

    return {
        "year": year_key,
        "score": round(total_risk, 1),
        "narrative": (
            "Low financial risk with stable income and manageable expenses."
            if total_risk < 30 else
            "Moderate financial risk — monitor debt levels and build emergency fund."
            if total_risk < 55 else
            "Elevated financial risk — prioritize debt reduction and income stability."
        ),
    }


# ── Health Formulas ──────────────────────────────────────────────────────

def compute_stress(
    profile: dict,
    context: dict,
    economic: dict,
    year_key: str,
) -> dict:
    """Stress = base + workload + financial_pressure + economic_pressure."""
    idx = _YEAR_INDICES.get(year_key, 0)
    t = idx + 1

    base_stress = 35.0
    work_hours = context.get("work_hours", 45)
    workload = max(0, (work_hours - 40) * 1.5)
    cpi = economic.get("inflation_cpi") or 4.95
    financial_pressure = max(0, (cpi - 4.0) * 3)
    unemp = economic.get("unemployment_rate") or 4.22
    economic_pressure = max(0, (unemp - 3.0) * 2)
    risk = context.get("risk_tolerance", "medium")
    risk_amplifier = {"low": 0.8, "medium": 1.0, "high": 1.3}.get(risk, 1.0)

    # Career acceleration years (Year3-Year7) are peak stress
    career_peak = 10 * math.sin(t * math.pi / 6) if t <= 5 else 5 * math.exp(-(t - 5) * 0.3)

    total = (base_stress + workload + financial_pressure + economic_pressure + career_peak) * risk_amplifier
    total = _clamp(total, 15, 95)

    narratives = [
        "Starting stress manageable — onboarding and learning curve.",
        "Performance pressure rising as expectations grow.",
        "Peak stress period — promotions and responsibility converge.",
        "Stress remains elevated but management improves with experience.",
        "Experience brings better stress management and perspective.",
    ]
    return {
        "year": year_key,
        "score": round(total, 1),
        "narrative": narratives[min(idx, 4)],
    }


def compute_burnout_risk(
    profile: dict,
    context: dict,
    economic: dict,
    year_key: str,
    stress_score: float = 50.0,
) -> dict:
    """Burnout risk = stress × workload / recovery capacity."""
    idx = _YEAR_INDICES.get(year_key, 0)
    work_hours = context.get("work_hours", 45)
    workload_factor = work_hours / 40.0
    recovery = 1.0 + (0.1 if context.get("location") in ("Bangalore", "Mumbai", "Pune") else 0.0)

    risk = (stress_score / 100.0) * workload_factor * 70.0 / recovery
    risk += 5 * max(0, idx - 1)  # cumulative fatigue
    risk = _clamp(risk, 10, 95)

    narratives = [
        "Low burnout risk in early career — manageable workload.",
        "Moderate risk as responsibilities increase.",
        "Career acceleration phase increases burnout potential significantly.",
        "Mid-career pressure point — highest risk period.",
        "Risk stabilizes as seniority brings autonomy and perspective.",
    ]
    return {
        "year": year_key,
        "risk": round(risk, 1),
        "narrative": narratives[min(idx, 4)],
    }


def compute_work_life_balance(
    profile: dict,
    context: dict,
    year_key: str,
) -> dict:
    """Work-life balance = recovery capacity / career intensity."""
    idx = _YEAR_INDICES.get(year_key, 0)
    work_hours = context.get("work_hours", 45)
    hours_penalty = max(0, (work_hours - 40) * 2)
    location = context.get("location", "India")
    city_living = 1.1 if location in ("Bangalore", "Mumbai", "Delhi") else 1.0

    base = 70.0
    career_intensity = 12 * math.sin(idx * math.pi / 4) if idx <= 3 else 5
    score = (base - hours_penalty - career_intensity) * city_living
    # Recovery after Year7
    if idx >= 3:
        score += 8 * (idx - 2)
    score = _clamp(score, 20, 90)

    narratives = [
        "Good balance — entry roles have clearer boundaries.",
        "Balance tipping as career demands increase.",
        "Most challenging period for work-life integration.",
        "Slowly regaining balance through better boundaries.",
        "Seniority brings schedule flexibility and control.",
    ]
    return {
        "year": year_key,
        "score": round(score, 1),
        "narrative": narratives[min(idx, 4)],
    }


def compute_physical_health(
    profile: dict,
    context: dict,
    year_key: str,
    stress_score: float = 50.0,
) -> dict:
    """Physical health decays with stress, improves with location amenities."""
    idx = _YEAR_INDICES.get(year_key, 0)
    base = 72.0
    stress_decay = max(0, (stress_score - 40) * 0.3)
    lifestyle = context.get("interests", "")
    exercise_bonus = 5 if any(a in lifestyle.lower() for a in ("gym", "sport", "yoga", "run", "fit")) else 0
    location = context.get("location", "India")
    pollution_penalty = 5 if location == "Delhi" else 0

    score = base - stress_decay * (idx + 1) * 0.3 + exercise_bonus - pollution_penalty
    score = _clamp(score, 25, 90)

    return {
        "year": year_key,
        "score": round(score, 1),
        "narrative": (
            "Good health — active lifestyle and manageable stress."
            if score > 60 else
            "Health declining — sedentary pattern and career stress taking toll."
            if score > 40 else
            "Health concerns — prioritize medical checkups and lifestyle changes."
        ),
    }


def compute_mental_health(
    profile: dict,
    context: dict,
    year_key: str,
    stress_score: float = 50.0,
    burnout_risk: float = 35.0,
) -> dict:
    """Mental health inversely correlated with stress and burnout."""
    idx = _YEAR_INDICES.get(year_key, 0)
    base = 65.0
    stress_impact = max(0, (stress_score - 35) * 0.4)
    burnout_impact = burnout_risk * 0.2
    social_buffer = context.get("location") in ("Bangalore", "Mumbai", "Pune", "Hyderabad")

    score = base - stress_impact - burnout_impact + (5 if social_buffer else 0)
    if idx >= 3:
        score += 4  # mental resilience builds
    score = _clamp(score, 20, 95)

    return {
        "year": year_key,
        "score": round(score, 1),
        "narrative": (
            "Good mental health — low stress, strong support system."
            if score > 65 else
            "Moderate mental health — monitor stress and maintain social connections."
            if score > 45 else
            "Mental health under strain — consider therapy and stress management."
        ),
    }


# ── Relationship Formulas ────────────────────────────────────────────────

def compute_family_stability(
    profile: dict,
    context: dict,
    year_key: str,
) -> dict:
    """Family stability affected by location, work hours, and time."""
    idx = _YEAR_INDICES.get(year_key, 0)
    location = context.get("location", "India")
    work_hours = context.get("work_hours", 45)

    proximity = 1.0 if location in ("Delhi", "Mumbai", "Bangalore", "Pune", "Chennai", "Hyderabad") else 0.7
    time_penalty = max(0, (work_hours - 40) * 0.5)
    base = 58.0
    score = base * proximity - time_penalty + idx * 1.5
    if idx >= 2:
        score += 5  # Stabilization after relocation
    score = _clamp(score, 20, 90)

    narratives = [
        "Relocating requires rebuilding family proximity deliberately.",
        "Regular visits and calls maintain family bonds.",
        "Family relationships stabilizing with established routines.",
        "Deepened appreciation for family as career matures.",
        "Strong family foundation — you have learned to prioritize.",
    ]
    return {
        "year": year_key,
        "score": round(score, 1),
        "narrative": narratives[min(idx, 4)],
    }


def compute_social_connection(
    profile: dict,
    context: dict,
    year_key: str,
) -> dict:
    """Social connections grow then stabilize, affected by work intensity."""
    idx = _YEAR_INDICES.get(year_key, 0)
    location = context.get("location", "India")
    urban_bonus = 1.15 if location in ("Bangalore", "Mumbai", "Delhi") else 1.0
    work_hours = context.get("work_hours", 45)
    time_penalty = max(0, (work_hours - 40) * 0.3)

    score = _growth_curve(50.0, 0.2, idx + 1, 80.0) * urban_bonus - time_penalty
    if idx >= 3:
        score -= 3  # Career peak reduces social time
    score = _clamp(score, 20, 90)

    narratives = [
        "Building social circle from scratch in new city.",
        "Core friend group formed through work and shared interests.",
        "Stable social network — deeper friendships forming.",
        "Career demands competing with social time — intentional effort needed.",
        "Rich social fabric — lifelong friends and community roots established.",
    ]
    return {
        "year": year_key,
        "score": round(score, 1),
        "narrative": narratives[min(idx, 4)],
    }


def compute_relationship_wealth(
    profile: dict,
    context: dict,
    family_score: float = 55.0,
    social_score: float = 58.0,
) -> dict:
    """Composite relationship wealth index."""
    love = family_score * 0.4 + social_score * 0.4
    location_bonus = 2 if context.get("location") in ("Bangalore", "Mumbai", "Pune", "Hyderabad") else 0
    return {
        "index": round(_clamp(love + location_bonus), 1),
        "narrative": (
            "Strong relationship foundation across family and social circles."
            if love > 60 else
            "Moderate relationship health — invest in key connections."
            if love > 40 else
            "Relationships need attention — prioritize connection time."
        ),
    }


# ── Opportunity Formulas ─────────────────────────────────────────────────

def compute_career_opportunities(
    profile: dict,
    context: dict,
    economic: dict,
) -> list:
    """Generate career opportunity timeline based on market conditions."""
    if not isinstance(economic, dict):
        logger.error("compute_career_opportunities received non-dict economic: %s", type(economic))
        economic = {}
    if not isinstance(context, dict):
        logger.error("compute_career_opportunities received non-dict context: %s", type(context))
        context = {}
    industry_health = (economic.get("industry_health") or 78) / 100.0
    automation_risk = economic.get("automation_risk", 15) / 100.0
    location = context.get("location", "India")
    loc_mult = 1.2 if location in ("Bangalore", "Mumbai", "Hyderabad") else 1.0

    opportunities = [
        {
            "year": "Year2",
            "title": "Senior Role at Product Company",
            "probability": round(0.55 * industry_health * loc_mult, 2),
            "impact_score": round(65 * industry_health),
            "description": "Move from services to product for better growth and compensation.",
        },
        {
            "year": "Year5",
            "title": "Engineering Manager",
            "probability": round(0.40 * industry_health * loc_mult, 2),
            "impact_score": round(75 * industry_health),
            "description": "First leadership role managing a team of 4-8 engineers.",
        },
        {
            "year": "Year8",
            "title": "Director/Head of Engineering",
            "probability": round(0.25 * industry_health * loc_mult * (1 - automation_risk), 2),
            "impact_score": round(85 * industry_health),
            "description": "Senior leadership role shaping engineering strategy.",
        },
    ]
    return opportunities


def compute_opportunity_score_forecast(
    profile: dict,
    context: dict,
    economic: dict,
) -> list:
    """Opportunity score = market opportunities × personal readiness."""
    if not isinstance(economic, dict):
        logger.error("compute_opportunity_score_forecast received non-dict economic: %s", type(economic))
        economic = {}
    if not isinstance(context, dict):
        logger.error("compute_opportunity_score_forecast received non-dict context: %s", type(context))
        context = {}
    industry_health = (economic.get("industry_health") or 78) / 100.0
    unemp = economic.get("unemployment_rate") or 4.22
    gdp = economic.get("gdp_growth") or 6.49
    location = context.get("location", "India")
    loc_bonus = 1.15 if location in ("Bangalore", "Mumbai", "Hyderabad", "Delhi") else 1.0

    forecasts = []
    for year_key in _YEARS:
        idx = _YEAR_INDICES.get(year_key, 0)
        market = industry_health * (1 + (gdp - 5) * 0.05) * loc_bonus
        experience = _growth_curve(50.0, 0.15, idx + 1, 85.0)
        score = market * 40 + experience * 0.6
        score -= max(0, (unemp - 5) * 3)  # Unemployment penalty
        forecasts.append({
            "year": year_key,
            "score": round(_clamp(score, 10, 95), 1),
        })
    return forecasts


# ── Economic Forecast Formulas ───────────────────────────────────────────

def compute_gdp_forecast(economic: dict) -> list:
    """GDP moderates over time from current rate toward long-term trend."""
    if not isinstance(economic, dict):
        logger.error("compute_gdp_forecast received non-dict: %s", type(economic))
        economic = {}
    gdp = economic.get("gdp_growth") or 6.49
    forecasts = []
    for year_key in _YEARS:
        idx = _YEAR_INDICES.get(year_key, 0)
        decay = math.exp(-idx * 0.05)
        value = 4.5 + (gdp - 4.5) * decay + random_noise(0.15)
        forecasts.append({
            "year": year_key,
            "value": round(value, 2),
            "narrative": (
                "GDP growth at current trajectory, above global average."
                if value > 5 else
                "GDP moderating toward trend growth rate."
            ),
        })
    return forecasts


def compute_salary_growth_forecast(
    profile: dict,
    context: dict,
    economic: dict,
) -> list:
    """Salary growth accelerates through mid-career, then stabilizes."""
    if not isinstance(economic, dict):
        logger.error("compute_salary_growth_forecast received non-dict economic: %s", type(economic))
        economic = {}
    if not isinstance(context, dict):
        logger.error("compute_salary_growth_forecast received non-dict context: %s", type(context))
        context = {}
    gdp = economic.get("gdp_growth") or 6.49
    industry_health = (economic.get("industry_health") or 78) / 100.0
    career_stage = context.get("career_stage", "early")

    stage_mult = {"early": 0.8, "mid": 1.2, "senior": 1.0, "late": 0.7}.get(career_stage, 1.0)
    forecasts = []
    for year_key in _YEARS:
        idx = _YEAR_INDICES.get(year_key, 0)
        base = 7.0
        peak = 12.0 * industry_health * stage_mult
        value = base + (peak - base) * math.sin(min(idx, 3) * math.pi / 6)
        if idx >= 3:
            value = peak * math.exp(-(idx - 2) * 0.15)
        forecasts.append({
            "year": year_key,
            "value": round(value, 1),
            "narrative": (
                "Entry-level salary growth above inflation."
                if idx == 0 else
                "Mid-level promotions driving salary acceleration."
                if idx <= 2 else
                "Senior-level compensation growth stabilizing."
            ),
        })
    return forecasts


# ── Core Simulation Formulas ─────────────────────────────────────────────

def compute_year_scores(
    profile: dict,
    context: dict,
    economic: dict,
    anchors: dict,
    year_key: str,
    personality_key: str = "B",
) -> dict:
    """
    Compute all 7 node scores for a single year.
    This is the core simulation formula.
    """
    idx = _YEAR_INDICES.get(year_key, 0)
    t = idx + 1

    # Personality biases
    personalities = {
        "A": {"income": -3, "career_growth": -5, "stress": -12, "health": 3, "relationships": 12, "happiness": 5, "opportunity": -8},
        "B": {"income": 2, "career_growth": 8, "stress": 2, "health": 0, "relationships": 0, "happiness": 2, "opportunity": 5},
        "C": {"income": 8, "career_growth": 6, "stress": 18, "health": -5, "relationships": -10, "happiness": -2, "opportunity": 15},
    }
    pb = personalities.get(personality_key, personalities["B"])

    industry_health = (economic.get("industry_health") or 78) / 100.0
    gdp = economic.get("gdp_growth") or 6.49
    unemp = economic.get("unemployment_rate") or 4.22
    cpi = economic.get("inflation_cpi") or 4.95

    # Income: grows over time with industry + personality
    income_base = 25 + pb["income"]
    income_growth = (industry_health * 12 + gdp * 0.5) * (t ** 0.6)
    income = _clamp(income_base + income_growth + random_noise(3), 10, 95)

    # Career growth: logistic curve + personality
    cg_base = 30 + pb["career_growth"]
    cg = _growth_curve(cg_base, 0.2 * industry_health, t, 90.0) + pb["career_growth"] * 0.3
    cg = _clamp(cg, 15, 98)

    # Stress: peaks mid-career
    stress = compute_stress(profile, context, economic, year_key)["score"] + pb["stress"] * 0.5
    stress = _clamp(stress, 15, 95)

    # Health: decays with stress
    health = 72 - max(0, (stress - 35) * 0.25) * (t ** 0.4) + pb["health"]
    health = _clamp(health, 20, 92)

    # Relationships: starts moderate, grows for Settler, declines for Gambler
    rel_base = 55 + pb["relationships"]
    if personality_key == "A":
        rel = _growth_curve(rel_base, 0.15, t, 85.0)
    elif personality_key == "C":
        rel = _decay_curve(rel_base, 0.10, t, 30.0)
    else:
        rel = _growth_curve(rel_base, 0.08, t, 75.0)
    rel = _clamp(rel, 20, 92)

    # Happiness: weighted combination
    happy = (
        health * 0.25 +
        rel * 0.20 +
        income * 0.20 +
        (100 - stress) * 0.20 +
        cg * 0.15
    ) + pb["happiness"]
    happy = _clamp(happy, 10, 98)

    # Opportunity: market-driven + personality
    opp_base = 50 + pb["opportunity"]
    opp = opp_base * industry_health * (1 - max(0, unemp - 4) * 0.03)
    opp += _growth_curve(0, 0.1, t, 20.0)
    if personality_key == "C":
        opp += 10 * math.sin(t * math.pi / 5)  # volatile
    opp = _clamp(opp, 15, 98)

    return {
        "income": round(income, 1),
        "career_growth": round(cg, 1),
        "stress": round(stress, 1),
        "health": round(health, 1),
        "relationships": round(rel, 1),
        "happiness": round(happy, 1),
        "opportunity": round(opp, 1),
    }


def random_noise(std: float = 2.0) -> float:
    """Deterministic noise using a simple sinusoidal hash."""
    import hashlib
    return (hashlib.md5(str(std).encode()).hexdigest()[0] == "a") * std * 0.5


# ── Confidence Formulas ──────────────────────────────────────────────────

def compute_confidence(
    data_quality: float,
    economic_certainty: float,
    simulation_variance: float,
    agent_agreement: float,
) -> dict:
    """
    Overall confidence = weighted combination of four factors.

    Parameters:
        data_quality: 0-100 (how complete/reliable input data is)
        economic_certainty: 0-100 (how stable/predictable economic indicators are)
        simulation_variance: 0-100 inverted (low variance = high score)
        agent_agreement: 0-100 (how much agents agree)
    """
    weights = {
        "data_quality": 0.30,
        "economic_certainty": 0.25,
        "simulation_variance": 0.25,
        "agent_agreement": 0.20,
    }

    overall = (
        data_quality * weights["data_quality"] +
        economic_certainty * weights["economic_certainty"] +
        (100 - simulation_variance) * weights["simulation_variance"] +
        agent_agreement * weights["agent_agreement"]
    )
    overall = _clamp(overall, 0, 100)

    tier = "high" if overall >= 75 else "medium" if overall >= 50 else "low"

    return {
        "overall": round(overall, 1),
        "tier": tier,
        "components": {
            "data_quality": round(data_quality, 1),
            "economic_certainty": round(economic_certainty, 1),
            "simulation_variance": round(simulation_variance, 1),
            "agent_agreement": round(agent_agreement, 1),
        },
        "uncertainty_drivers": _get_uncertainty_drivers(
            data_quality, economic_certainty,
            simulation_variance, agent_agreement,
        ),
    }


def _get_uncertainty_drivers(
    data_quality: float,
    economic_certainty: float,
    simulation_variance: float,
    agent_agreement: float,
) -> list:
    drivers = []
    if data_quality < 60:
        drivers.append("Limited input data reduces prediction reliability.")
    if economic_certainty < 50:
        drivers.append("High economic volatility increases uncertainty.")
    if simulation_variance > 40:
        drivers.append("Wide simulation variance indicates path sensitivity.")
    if agent_agreement < 50:
        drivers.append("Agent disagreement reflects genuine trade-off complexity.")
    if not drivers:
        drivers.append("High confidence across all dimensions.")
    return drivers
