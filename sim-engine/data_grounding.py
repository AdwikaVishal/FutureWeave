import logging
import os
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_LIVE_DATA_AVAILABLE = False
try:
    from real_data_provider import get_live_grounding
    _LIVE_DATA_AVAILABLE = True
except ImportError:
    logger.warning("[Grounding] real_data_provider not found")

LOCATION_MAP = {
    "bengaluru":  "Bangalore",
    "bangalore":  "Bangalore",
    "hydrabad":   "Hyderabad",
    "hyderabad":  "Hyderabad",
    "mumbai":     "Mumbai",
    "bombay":     "Mumbai",
    "delhi":      "Delhi",
    "new delhi":  "Delhi",
    "pune":       "Pune",
    "chennai":    "Chennai",
    "madras":     "Chennai",
}

INDUSTRY_KEYWORDS = {
    "software":      ["software", "developer", "programmer", "coder",
                      "tech", "it", "startup", "saas", "app"],
    "finance":       ["finance", "banking", "investment", "accountant", "trader", "analyst"],
    "healthcare":    ["doctor", "nurse", "medical", "health", "pharma", "hospital"],
    "manufacturing": ["mechanical", "manufacturing", "production", "factory", "industrial"],
    "education":     ["teacher", "professor", "education", "school", "college", "university"],
    "retail":        ["retail", "sales", "store", "shop", "merchant"],
}

ROLE_KEYWORDS = {
    "software engineer": ["software", "developer", "programmer", "coder",
                          "web developer", "app developer", "backend", "frontend"],
    "data scientist":    ["data scientist", "data analyst", "machine learning",
                          "ml engineer", "ai", "deep learning"],
    "product manager":   ["product manager", "product owner", "pm "],
    "mechanical engineer": ["mechanical", "mechanical engineer"],
    "designer":          ["designer", "ui/ux", "graphic designer", "product designer"],
}

EDUCATION_FIELDS = {
    "computer science": ["computer science", "cse", "computer engineering"],
    "aiml":             ["aiml", "ai/ml", "artificial intelligence", "machine learning"],
    "electrical engineering": ["electrical engineering", "eee", "ece", "electronics"],
    "mechanical engineering": ["mechanical engineering", "mechanical"],
}

EDUCATION_KEYWORDS = [
    " at ", " in ", " college ", " university ", " institute ",
    "vit", "iit", "nit", "iiit", "btech", "mtech", "degree", "course",
    "study", "program", "admission", "neet", "jee", "gate", "cat",
    "xat", "clat", "upsc", "ssc", "ibps",
]

PSYCHOGRAPHIC_BASE_RATES = {
    "stress":        55,
    "health":        65,
    "relationships": 60,
    "happiness":     52,
}


def _whole_word_match(word: str, text: str) -> bool:
    pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
    return bool(pattern.search(text))


def _any_whole_word_match(keywords: list[str], text: str) -> bool:
    return any(_whole_word_match(kw, text) for kw in keywords)


def detect_industry(decision: str, context: dict) -> str:
    text = decision + " " + str(context)
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if _any_whole_word_match(keywords, text):
            return industry
    return "default"


def detect_role(decision: str, context: dict) -> str:
    text = decision + " " + str(context)
    for role, keywords in ROLE_KEYWORDS.items():
        if _any_whole_word_match(keywords, text):
            return role
    return "default"


def is_educational_decision(decision: str) -> bool:
    text = decision.lower()
    return any(kw in text for kw in EDUCATION_KEYWORDS)


def detect_education_field(decision: str, context: dict) -> str | None:
    text = decision + " " + str(context)
    for field, keywords in EDUCATION_FIELDS.items():
        if _any_whole_word_match(keywords, text):
            return field
    return None


def detect_education_fields(decision: str, context: dict) -> list[str]:
    text = decision + " " + str(context)
    found = []
    for field, keywords in EDUCATION_FIELDS.items():
        if _any_whole_word_match(keywords, text):
            found.append(field)
    return found


def normalise_location(raw: str) -> str:
    if not isinstance(raw, str):
        return "India"
    lower = raw.lower()
    for key, canonical in LOCATION_MAP.items():
        if key in lower:
            return canonical
    return "India"


MONTHLY_EXPENSE_BASE = {
    "Bangalore": 35_000,
    "Mumbai":    45_000,
    "Delhi":     38_000,
    "Hyderabad": 30_000,
    "Pune":      32_000,
    "Chennai":   28_000,
    "India":     22_000,
}

STALE_DATA_THRESHOLDS = {
    "salary": 90,
    "job_market": 7,
    "cost_of_living": 180,
    "macro": 365,
}


def check_data_freshness(dataset_type: str, fetched_at_str: str | None) -> dict:
    if not fetched_at_str:
        return {
            "fresh": False,
            "stale": True,
            "reason": "no_timestamp",
            "age_days": None,
            "max_age_days": STALE_DATA_THRESHOLDS.get(dataset_type),
        }
    try:
        fetched_at = datetime.fromisoformat(fetched_at_str)
        age = datetime.now(timezone.utc) - fetched_at
        age_days = age.days
        max_age = STALE_DATA_THRESHOLDS.get(dataset_type)
        if max_age and age_days > max_age:
            return {
                "fresh": False,
                "stale": True,
                "reason": f"data_age_{age_days}d_exceeds_{max_age}d_threshold",
                "age_days": age_days,
                "max_age_days": max_age,
            }
        return {
            "fresh": True,
            "stale": False,
            "age_days": age_days,
            "max_age_days": max_age,
        }
    except Exception:
        return {"fresh": False, "stale": True, "reason": "parse_error"}


def get_grounding_data(decision: str, context: dict) -> dict:
    try:
        role = detect_role(decision, context)
        industry = detect_industry(decision, context)
        location = normalise_location(context.get("location", "India"))
        is_edu = is_educational_decision(decision)
        edu_fields = detect_education_fields(decision, context)

        snapshot = context.get("_economic_snapshot") or {}
        snapshot_grounding = snapshot.get("grounding", {}) if isinstance(snapshot, dict) else {}
        live_salary_range = None
        live_cpi = None
        live_unemployment = None
        live_gdp_growth = None
        data_source = None
        cpi_source = None
        cpi_year = None
        confidence = None
        data_warnings = []
        monitoring = {}
        source_attribution = {}
        data_freshness = {}

        decision_type = snapshot.get("decision_type", "general") if isinstance(snapshot, dict) else "general"

        if isinstance(snapshot, dict):
            confidence = snapshot.get("confidence")
            data_warnings = snapshot.get("messages", [])
            monitoring = snapshot.get("monitoring", {}) or {}
            source_attribution = snapshot.get("source_attribution", {}) or {}
            data_freshness = snapshot.get("data_freshness", {}) or {}

        if snapshot_grounding:
            live_salary_range = snapshot_grounding.get("live_salary_range")
            live_cpi = snapshot_grounding.get("live_cpi")
            live_unemployment = snapshot_grounding.get("live_unemployment")
            live_gdp_growth = snapshot_grounding.get("live_gdp_growth")
            data_source = snapshot_grounding.get("salary_source")
            cpi_source = snapshot_grounding.get("cpi_source", "world_bank")
            cpi_year = snapshot_grounding.get("cpi_year")

        if not snapshot_grounding and _LIVE_DATA_AVAILABLE:
            indeed_key = os.environ.get("INDEED_API_KEY", "")
            rapid_key = os.environ.get("RAPIDAPI_KEY", "")
            live = get_live_grounding(role, location, indeed_key, rapid_key)

            live_salary_range = live.get("live_salary_range")
            live_cpi = live.get("live_cpi")
            live_unemployment = live.get("live_unemployment")
            live_gdp_growth = live.get("live_gdp_growth")
            data_source = live.get("salary_source")
            cpi_source = live.get("cpi_source", "world_bank")
            cpi_year = live.get("cpi_year")

        employment = None
        if live_unemployment is not None:
            employment = max(0.0, min(1.0, 1.0 - live_unemployment / 100.0))
            if live_unemployment is not None:
                logger.info("[Grounding] Live unemployment applied: %.1f%%", live_unemployment)

        col_index = None
        col_data = snapshot_grounding.get("cost_of_living_data") if snapshot_grounding else None
        if col_data:
            categories = col_data.get("rent", []) + col_data.get("groceries", []) + col_data.get("transport", []) + col_data.get("utilities", [])
            if categories:
                total = sum(c.get("price", 0) for c in categories)
                if total > 0:
                    col_index = round(total / 30000, 2)

        salary_entry = None
        salary_mid = None
        salary_senior = None
        if live_salary_range and live_salary_range[1] > 0:
            live_min, live_max = live_salary_range
            salary_entry = (live_min, live_min * 1.3)
            salary_mid = (live_min * 1.3, live_max * 0.7)
            salary_senior = (live_max * 0.7, live_max * 1.2)
            logger.info(
                "[Grounding] Live salary applied (%s): entry=%s mid=%s senior=%s",
                data_source, salary_entry, salary_mid, salary_senior,
            )

        return {
            "role": role,
            "industry": industry,
            "location": location,
            "salary_entry_lpa": salary_entry,
            "salary_mid_lpa": salary_mid,
            "salary_senior_lpa": salary_senior,
            "employment_rate": employment,
            "cost_of_living_index": col_index,
            "is_educational": is_edu,
            "education_fields": edu_fields,
            "live_salary_range": live_salary_range,
            "live_cpi": live_cpi,
            "live_unemployment": live_unemployment,
            "live_gdp_growth": live_gdp_growth,
            "data_source": data_source,
            "cpi_source": cpi_source,
            "cpi_year": cpi_year,
            "confidence": confidence,
            "data_warnings": data_warnings,
            "monitoring": monitoring,
            "source_attribution": source_attribution,
            "data_freshness": data_freshness,
            "decision_type": decision_type,
        }
    except Exception as exc:
        logger.warning("[Grounding] Failed: %s", exc)
        return {
            "role": "default",
            "industry": "default",
            "location": "India",
            "salary_entry_lpa": None,
            "salary_mid_lpa": None,
            "salary_senior_lpa": None,
            "employment_rate": None,
            "cost_of_living_index": None,
            "is_educational": False,
            "education_fields": [],
            "live_salary_range": None,
            "live_cpi": None,
            "live_unemployment": None,
            "live_gdp_growth": None,
            "data_source": None,
            "cpi_source": None,
            "cpi_year": None,
            "confidence": None,
            "data_warnings": ["Grounding data unavailable"],
            "monitoring": {},
            "source_attribution": {},
            "data_freshness": {},
            "decision_type": "general",
        }


def score_to_lpa(score, entry, mid, senior):
    if not entry or not mid or not senior:
        return None
    if entry[1] <= 0 or mid[1] <= 0 or senior[1] <= 0:
        return None
    if score <= 30:
        t = score / 30.0
        return round(entry[0] + t * (entry[1] - entry[0]), 1)
    if score <= 60:
        t = (score - 30) / 30.0
        return round(mid[0] + t * (mid[1] - mid[0]), 1)
    if score <= 85:
        t = (score - 60) / 25.0
        return round(senior[0] + t * (senior[1] - senior[0]), 1)
    t = (score - 85) / 15.0
    return round(senior[1] + t * (senior[1] * 0.5), 1)


def build_score_anchors(grounding: dict) -> dict:
    e = grounding.get("salary_entry_lpa")
    m = grounding.get("salary_mid_lpa")
    s = grounding.get("salary_senior_lpa")

    if not all([e, m, s]):
        return {
            "income_anchors": None,
            "opportunity_base": 50,
            "psychographic_bases": dict(PSYCHOGRAPHIC_BASE_RATES),
            "prompt_block": "WARNING: No live salary data available. Income estimates will be uncertain.",
            "salary_entry_lpa": None,
            "salary_mid_lpa": None,
            "salary_senior_lpa": None,
        }

    anchors = {
        10: score_to_lpa(10, e, m, s),
        25: score_to_lpa(25, e, m, s),
        40: score_to_lpa(40, e, m, s),
        55: score_to_lpa(55, e, m, s),
        70: score_to_lpa(70, e, m, s),
        85: score_to_lpa(85, e, m, s),
        100: score_to_lpa(100, e, m, s),
    }

    opp_base = 50
    emp = grounding.get("employment_rate")
    if emp is not None:
        opp_base = max(0, min(100, int(emp * 100)))

    psych = dict(PSYCHOGRAPHIC_BASE_RATES)

    live_lines = ""
    live_salary = grounding.get("live_salary_range")
    live_cpi = grounding.get("live_cpi")
    live_unemp = grounding.get("live_unemployment")
    live_gdp = grounding.get("live_gdp_growth")
    data_source = grounding.get("data_source")
    cpi_source = grounding.get("cpi_source", "static_default")

    if live_salary:
        live_lines += (
            f"  LIVE SALARY [{data_source or 'unknown'}]: "
            f"₹{live_salary[0]}–{live_salary[1]} LPA "
            f"for {grounding['role']} in {grounding['location']}\n"
        )
    if live_cpi is not None:
        live_lines += (
            f"  INFLATION [{cpi_source}]: {live_cpi:.1f}% annual CPI (HISTORICAL)\n"
        )
    if live_unemp is not None:
        live_lines += (
            f"  UNEMPLOYMENT [World Bank]: {live_unemp:.1f}% of labour force\n"
        )
    if live_gdp is not None:
        live_lines += (
            f"  GDP GROWTH [World Bank]: {live_gdp:.1f}% annual\n"
        )

    prompt_block = ""
    if live_lines:
        prompt_block += f"\nLIVE DATA:\n{live_lines}\n"
    else:
        prompt_block += "\nWARNING: No live data available. All values are uncertain.\n"

    prompt_block += (
        f"INCOME SCORE SCALE (only if salary data available):\n"
        f"  10 → {anchors[10]} LPA\n"
        f"  25 → {anchors[25]} LPA\n"
        f"  40 → {anchors[40]} LPA\n"
        f"  55 → {anchors[55]} LPA\n"
        f"  70 → {anchors[70]} LPA\n"
        f"  85 → {anchors[85]} LPA\n"
        f" 100 → {anchors[100]} LPA\n\n"
        f"OPPORTUNITY BASE: {opp_base}/100\n"
    )

    ps = grounding.get("psychographic_bases", psych)
    prompt_block += (
        f"PSYCHOGRAPHIC BASE RATES:\n"
        f"  stress: {ps.get('stress', 55)}/100\n"
        f"  health: {ps.get('health', 65)}/100\n"
        f"  relationships: {ps.get('relationships', 60)}/100\n"
        f"  happiness: {ps.get('happiness', 52)}/100\n\n"
        f"When outputting income scores, use the LPA scale above if available. "
        f"If no salary data is available, income scores should reflect the user's context, "
        f"NOT default values.\n"
    )

    return {
        "income_anchors": anchors,
        "opportunity_base": opp_base,
        "psychographic_bases": psych,
        "prompt_block": prompt_block,
        "salary_entry_lpa": e,
        "salary_mid_lpa": m,
        "salary_senior_lpa": s,
    }


def employment_rate_to_opportunity(rate: float) -> int:
    if rate is None:
        return 50
    return max(0, min(100, int(rate * 100)))


def compute_core_variables(grounding: dict, context: dict) -> dict:
    location = grounding.get("location", "India")
    entry = grounding.get("salary_entry_lpa")
    cpi = grounding.get("live_cpi")
    unemp_pct = grounding.get("live_unemployment")
    gdp_growth = grounding.get("live_gdp_growth")

    expected_lpa = None
    monthly_income = 0
    monthly_expenses = 0
    disposable = 0
    savings_rate = 0.0
    stress_score = 50
    gdp_opportunity_mod = 0

    if entry and entry[0] and entry[1]:
        skills_text = str(context.get("skills", "")).lower()
        skill_boost = 0.15 if any(
            kw in skills_text for kw in ["senior", "lead", "expert", "5+", "7+", "10+"]
        ) else 0.0
        expected_lpa = round(entry[0] + (entry[1] - entry[0]) * (0.5 + skill_boost), 2)
        expected_lpa = min(expected_lpa, entry[1])

        monthly_income = int(expected_lpa * 100_000 / 12)

    base_expense = MONTHLY_EXPENSE_BASE.get(location, MONTHLY_EXPENSE_BASE["India"])
    col_index = grounding.get("cost_of_living_index")
    cpi_factor = 1.0
    if cpi is not None:
        cpi_factor = 1 + cpi / 100
    elif col_index is not None:
        cpi_factor = col_index
    monthly_expenses = int(base_expense * cpi_factor)

    if monthly_income > 0:
        disposable = monthly_income - monthly_expenses
        if disposable > 0:
            savings_rate = round((disposable / monthly_income) * 100, 1)
    else:
        disposable = -monthly_expenses

    if monthly_income > 0:
        expense_ratio = monthly_expenses / monthly_income
    else:
        expense_ratio = 1.5
    financial_stress = min(33, int(expense_ratio * 33))

    unemp_stress = min(33, int(((unemp_pct or 5.0) / 20) * 33))
    cpi_stress = min(34, int(((cpi or 5.0) / 15) * 34))
    stress_score = min(100, financial_stress + unemp_stress + cpi_stress)

    if gdp_growth is not None:
        if gdp_growth >= 7.0:
            gdp_opportunity_mod = +5
        elif gdp_growth >= 5.0:
            gdp_opportunity_mod = 0
        elif gdp_growth >= 2.0:
            gdp_opportunity_mod = -5
        else:
            gdp_opportunity_mod = -10

    computed_block = (
        f"CORE VARIABLES (computed from live/context data):\n"
    )
    if expected_lpa:
        computed_block += f"  Expected Salary: ~₹{expected_lpa} LPA\n"
    else:
        computed_block += f"  Expected Salary: NO LIVE DATA - cannot compute\n"
    computed_block += (
        f"  Monthly Income: ~₹{monthly_income:,}\n"
        f"  Monthly Expenses: ~₹{monthly_expenses:,}\n"
        f"  Disposable Income: ~₹{disposable:,}/month\n"
        f"  Savings Rate: ~{savings_rate}%\n"
        f"  Stress Score: ~{stress_score}/100\n"
    )
    if gdp_opportunity_mod != 0:
        computed_block += f"  GDP Opportunity Modifier: {gdp_opportunity_mod:+d}\n"

    return {
        "expected_salary_lpa": expected_lpa,
        "monthly_income": monthly_income,
        "monthly_expenses": monthly_expenses,
        "disposable_income": disposable,
        "savings_rate_pct": savings_rate,
        "stress_score": stress_score,
        "gdp_opportunity_mod": gdp_opportunity_mod,
        "computed_block": computed_block,
    }
