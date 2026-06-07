from __future__ import annotations
import math
import logging
from typing import Any, Dict, List
from .types import (
    FuturePath, YearScores, EconomicData, UserProfile,
    DecisionOption, SIMULATION_YEARS,
)

logger = logging.getLogger(__name__)

_YEAR_INDICES = {yk: i for i, yk in enumerate(SIMULATION_YEARS)}


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _logistic(base: float, cap: float, rate: float, t: float) -> float:
    return base + (cap - base) * (1 - math.exp(-rate * t))


def compute_year_scores(
    profile: UserProfile,
    economic: EconomicData,
    year_key: str,
    option_bias: Dict[str, float],
) -> YearScores:
    idx = _YEAR_INDICES.get(year_key, 0)
    t = idx + 1
    risk = profile.risk_tolerance

    salary_score = economic.salary_score / 100.0
    economic_score = economic.economic_score / 100.0
    employment_score = economic.employment_score / 100.0
    industry_score = economic.industry_score / 100.0
    col_score = economic.cost_of_living_score / 100.0

    ind_health = economic.industry_health / 100.0
    gdp = economic.gdp_growth / 100.0
    infl = economic.inflation_cpi / 100.0
    sal_growth = economic.salary_growth_pct / 100.0
    col_index = economic.cost_of_living_index
    pb = option_bias

    effective_sal_growth = sal_growth * (0.5 + 0.3 * salary_score + 0.2 * industry_score)
    effective_ind_health = ind_health * (0.6 + 0.2 * industry_score + 0.2 * economic_score)
    effective_gdp = gdp * (0.7 + 0.3 * economic_score)
    employment_modifier = 0.8 + 0.4 * employment_score
    col_pressure = max(0, (col_index - 1.0) * 0.2)

    col_penalty_on_income = max(0, (col_index - 1.0) * 15)
    salary_bonus_on_income = (salary_score - 0.4) * 30
    loc_mod = 1.0 + (salary_bonus_on_income - col_penalty_on_income) / 100.0

    income = _clamp(_logistic(25, 95 * effective_ind_health, 0.3 * (1 + effective_sal_growth) * (1 + pb.get("income", 0)) * employment_modifier, t) * loc_mod)
    career_growth = _clamp(_logistic(20, 90, 0.25 * effective_ind_health * (1 + pb.get("career", 0)) * employment_modifier, t) * (0.7 + 0.3 * salary_score) - col_penalty_on_income * 2)
    stress = _clamp(40 + 30 * (1 - math.exp(-0.2 * t)) - 15 * pb.get("calm", 0) + 10 * risk + col_pressure * 20 + max(0, infl - 0.05) * 50)
    health = _clamp(70 - 10 * (1 - math.exp(-0.15 * t)) - 5 * stress / 100 + 8 * pb.get("health", 0) - col_pressure * 10)
    relationships = _clamp(60 - 8 * (1 - math.exp(-0.2 * t)) + 12 * pb.get("social", 0) - 3 * risk * 10 - col_pressure * 5)
    freedom = _clamp(50 + income * 0.2 - stress * 0.3 + career_growth * 0.1 + 15 * pb.get("freedom", 0) + economic_score * 10)
    purpose = _clamp(30 + career_growth * 0.25 + (100 - stress) * 0.15 + relationships * 0.15 + 10 * pb.get("purpose", 0) + economic_score * 8)
    learning_growth = _clamp(35 + career_growth * 0.3 + (1 - risk) * 10 + 8 * pb.get("learning", 0) + employment_score * 10)
    social_support = _clamp(40 + relationships * 0.4 + (100 - stress) * 0.2 + 10 * pb.get("social", 0))
    burnout_risk = _clamp(stress * 0.5 + (100 - health) * 0.3 + (100 - freedom) * 0.2)

    happiness = _clamp(
        50 + 0.12 * (income - 50) + 0.15 * (health - 50) + 0.2 * (relationships - 50)
        + 0.12 * (career_growth - 50) + 0.1 * (purpose - 50)
        - 0.1 * stress + 5 * pb.get("happiness", 0) + effective_gdp * 5 - col_pressure * 5
    )

    opportunity = _clamp(30 + career_growth * 0.35 + risk * 15 + effective_ind_health * 10 + 10 * pb.get("opportunity", 0) + economic_score * 10 + employment_score * 5)
    regret = _clamp(20 + (100 - happiness) * 0.3 + (100 - purpose) * 0.2 + stress * 0.2 + max(0, 50 - income) * 0.1)

    salary_multiplier = 0.7 + 0.3 * salary_score
    base_salary = (6 + (income / 100) * 34) * salary_multiplier
    effective_savings_rate = max(0, 0.3 - infl * 0.5 - 0.05 * profile.dependents - col_pressure * 0.3)
    savings = base_salary * effective_savings_rate * t * (1 + effective_sal_growth) ** t
    net_worth = savings * (1 + max(0, (economic.interest_rate - infl * 100) / 100)) ** t
    risk_exposure = 100 - (happiness * 0.3 + health * 0.3 + relationships * 0.2 + career_growth * 0.2)

    return YearScores(
        income=round(income, 1), career_growth=round(career_growth, 1),
        stress=round(stress, 1), health=round(health, 1),
        relationships=round(relationships, 1), happiness=round(happiness, 1),
        opportunity=round(opportunity, 1), savings=round(savings, 1),
        net_worth=round(net_worth, 1), risk_exposure=round(_clamp(risk_exposure), 1),
        purpose=round(purpose, 1), freedom=round(freedom, 1),
        regret=round(regret, 1), burnout_risk=round(burnout_risk, 1),
        learning_growth=round(learning_growth, 1),
        social_support=round(social_support, 1),
    )


def _option_bias(key: str) -> Dict[str, float]:
    biases = {
        "Stay in Corporate": {"income": 0.0, "career": 0.05, "calm": 0.2, "health": 0.1, "social": 0.1, "happiness": 0.05, "opportunity": -0.1, "freedom": -0.1, "purpose": -0.05, "learning": 0.0},
        "Join Startup": {"income": -0.1, "career": 0.2, "calm": -0.15, "health": -0.05, "social": 0.0, "happiness": 0.1, "opportunity": 0.25, "freedom": -0.05, "purpose": 0.15, "learning": 0.25},
        "Start Company": {"income": -0.2, "career": 0.3, "calm": -0.3, "health": -0.15, "social": -0.1, "happiness": 0.15, "opportunity": 0.35, "freedom": 0.25, "purpose": 0.3, "learning": 0.3},
        "Pursue MBA": {"income": -0.15, "career": 0.25, "calm": 0.05, "health": 0.0, "social": 0.2, "happiness": 0.05, "opportunity": 0.2, "freedom": -0.1, "purpose": 0.1, "learning": 0.35},
        "Move Abroad": {"income": 0.1, "career": 0.15, "calm": -0.2, "health": -0.05, "social": -0.25, "happiness": 0.1, "opportunity": 0.2, "freedom": 0.15, "purpose": 0.1, "learning": 0.2},
        "Switch Careers": {"income": -0.15, "career": 0.15, "calm": -0.1, "health": -0.05, "social": 0.0, "happiness": 0.1, "opportunity": 0.15, "freedom": 0.05, "purpose": 0.2, "learning": 0.3},
        "Work Remotely": {"income": -0.05, "career": -0.1, "calm": 0.25, "health": 0.1, "social": -0.1, "happiness": 0.2, "opportunity": -0.05, "freedom": 0.35, "purpose": 0.05, "learning": -0.05},
        "Take Gap Year": {"income": -0.3, "career": -0.2, "calm": 0.35, "health": 0.2, "social": 0.15, "happiness": 0.25, "opportunity": -0.1, "freedom": 0.4, "purpose": 0.2, "learning": 0.15},
        "Buy House": {"income": 0.0, "career": 0.0, "calm": 0.15, "health": 0.05, "social": 0.1, "happiness": 0.1, "opportunity": -0.1, "freedom": -0.2, "purpose": 0.05, "learning": -0.1},
        "Default": {"income": 0.0, "career": 0.0, "calm": 0.1, "health": 0.05, "social": 0.05, "happiness": 0.05, "opportunity": 0.0, "freedom": 0.0, "purpose": 0.0, "learning": 0.0},
    }
    return biases.get(key, biases["Default"])


def _compute_case(ys: YearScores) -> Dict[str, float]:
    return {
        "income": ys.income, "career_growth": ys.career_growth,
        "happiness": ys.happiness, "net_worth": ys.net_worth,
        "purpose": ys.purpose, "freedom": ys.freedom,
    }


def generate_future_paths(profile: UserProfile, economic: EconomicData, options: List[DecisionOption]) -> Dict[str, FuturePath]:
    paths = {}
    for opt in options:
        bias = _option_bias(opt.title)
        years = {}
        all_events = []
        for yk in SIMULATION_YEARS:
            years[yk] = compute_year_scores(profile, economic, yk, bias)
            all_events.extend(_generate_events(yk, profile, economic, opt))

        scores = [years[yk].happiness for yk in SIMULATION_YEARS]
        final = sum(scores) / len(scores) if scores else 50

        ly = years.get("Year20") or years.get("Year10")
        if ly:
            best = _compute_case(years.get("Year20") or years.get("Year10"))
            expected = _compute_case(years.get("Year10") or years.get("Year5"))
            worst = _compute_case(years.get("Year1"))
        else:
            best = expected = worst = {"income": 50, "career_growth": 50, "happiness": 50, "net_worth": 0, "purpose": 50, "freedom": 50}

        summary = _generate_summary(opt.title, years)
        paths[opt.title] = FuturePath(
            option_key=opt.title, label=opt.title,
            archetype=opt.risk_level.title(),
            years=years, events=all_events,
            final_score=round(final, 1),
            best_case=best, expected_case=expected, worst_case=worst,
            summary=summary,
        )

    logger.info("[FutureSimulator] Generated %d future paths", len(paths))
    for key, p in paths.items():
        logger.info("[FutureSimulator] %s: final=%.1f Y10 income=%.1f happy=%.1f",
                    key, p.final_score,
                    p.years.get("Year10", YearScores()).income,
                    p.years.get("Year10", YearScores()).happiness)
    return paths


def _generate_events(year_key: str, profile: UserProfile, economic: EconomicData, option: DecisionOption) -> list:
    events = []
    economic_score = economic.economic_score / 100.0
    events_map = {
        "Year1": [{"year": "Year1", "type": "milestone", "name": f"Started: {option.title}", "impact": "neutral", "description": f"Embarked on the {option.title.lower()} path."}],
        "Year3": [{"year": "Year3", "type": "career", "name": "First major checkpoint", "impact": "positive" if option.risk_level in ("high", "moderate") else "neutral", "description": "Career progression review and skill assessment."}],
        "Year5": [{"year": "Year5", "type": "financial", "name": "Wealth inflection point", "impact": "positive", "description": "Savings and investments reach meaningful scale after 5 years."}],
        "Year10": [{"year": "Year10", "type": "life", "name": "Decade milestone", "impact": "positive" if option.upside_potential != "low" else "mixed", "description": "Ten-year reflection reveals whether the bet paid off."}],
        "Year20": [{"year": "Year20", "type": "life", "name": "Long-term outcome", "impact": "positive" if economic_score > 0.5 else "mixed", "description": "Two decades later — the compound effect of this decision is clear."}],
    }
    base = events_map.get(year_key, [])
    events.extend(base)
    if economic_score < 0.4 and year_key == "Year3":
        events.append({"year": "Year3", "type": "economic", "name": "Economic headwind", "impact": "negative", "description": "Economic slowdown creates headwinds for this path."})
    if economic_score > 0.7 and year_key == "Year5":
        events.append({"year": "Year5", "type": "economic", "name": "Growth tailwind", "impact": "positive", "description": "Strong economic growth accelerates progress on this path."})
    if option.risk_level == "high" and year_key == "Year5":
        events.append({"year": "Year5", "type": "risk", "name": "Risk event probability", "impact": "negative", "description": "High-risk paths face elevated uncertainty at the 5-year mark."})
    return events


def _generate_summary(option_title: str, years: Dict[str, YearScores]) -> str:
    y1 = years.get("Year1")
    y10 = years.get("Year10")
    y20 = years.get("Year20")
    if y1 and y10:
        happy_delta = y10.happiness - y1.happiness
        income_delta = y10.income - y1.income
        trend = "strongly positive" if happy_delta > 15 else "positive" if happy_delta > 5 else "mixed" if happy_delta > -5 else "challenging"
        return f"On the '{option_title}' path, happiness {('rises by ' + str(round(happy_delta)) + 'pts') if happy_delta > 0 else ('declines by ' + str(round(abs(happy_delta))) + 'pts')} over 10 years. Income {('grows by ' + str(round(income_delta)) + 'pts') if income_delta > 0 else ('declines by ' + str(round(abs(income_delta))) + 'pts')}. The overall trajectory is {trend}."
    return f"On the '{option_title}' path, outcomes develop over time with compounding effects."
