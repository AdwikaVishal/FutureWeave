"""
Real-world data grounding for timeline generation.

Provides:
- Salary ranges (LPA) by role + location  (live API → static fallback)
- Employment rates by industry             (live World Bank → static fallback)
- Cost of living indices
- Score ↔ real-world value conversion utilities
- Psychographic base rates (stress, health, relationships, happiness)
  sourced from published India workforce surveys.

Live data is fetched via real_data_provider.py when API keys are present
in the environment.  All live calls are cached for 24 hours.
"""
import logging
import os

logger = logging.getLogger(__name__)

# ── Live data integration (optional — degrades gracefully without keys) ───────
try:
    from real_data_provider import get_live_grounding
    _LIVE_DATA_AVAILABLE = True
except ImportError:
    _LIVE_DATA_AVAILABLE = False
    logger.warning("[Grounding] real_data_provider not found — using static data only")

# ── Salary database (LPA = Lakhs Per Annum) ──────────────────────────────────
SALARY_DATABASE = {
    "software engineer": {
        "India":     {"entry": (4, 8),   "mid": (10, 20), "senior": (20, 50)},
        "Bangalore": {"entry": (6, 12),  "mid": (15, 30), "senior": (30, 80)},
        "Hyderabad": {"entry": (5, 10),  "mid": (12, 25), "senior": (25, 60)},
        "Mumbai":    {"entry": (6, 12),  "mid": (14, 28), "senior": (28, 70)},
        "Delhi":     {"entry": (5, 11),  "mid": (12, 26), "senior": (26, 65)},
        "Pune":      {"entry": (5, 10),  "mid": (12, 24), "senior": (24, 55)},
        "Chennai":   {"entry": (4, 9),   "mid": (10, 22), "senior": (22, 50)},
    },
    "mechanical engineer": {
        "India":     {"entry": (3, 6),   "mid": (7, 14),  "senior": (15, 30)},
        "Bangalore": {"entry": (4, 7),   "mid": (8, 16),  "senior": (18, 35)},
        "Chennai":   {"entry": (3, 6),   "mid": (7, 14),  "senior": (15, 28)},
    },
    "data scientist": {
        "India":     {"entry": (6, 10),  "mid": (12, 22), "senior": (25, 60)},
        "Bangalore": {"entry": (8, 14),  "mid": (15, 30), "senior": (30, 80)},
    },
    "product manager": {
        "India":     {"entry": (8, 14),  "mid": (15, 30), "senior": (30, 70)},
        "Bangalore": {"entry": (10, 18), "mid": (20, 40), "senior": (40, 100)},
    },
    "designer": {
        "India":     {"entry": (4, 8),   "mid": (8, 16),  "senior": (18, 40)},
        "Bangalore": {"entry": (5, 10),  "mid": (10, 20), "senior": (22, 50)},
    },
    "default": {
        "India":     {"entry": (3, 7),   "mid": (7, 15),  "senior": (15, 35)},
    },
}

# ── Employment rates by industry ──────────────────────────────────────────────
EMPLOYMENT_RATES = {
    "software":      0.92,
    "tech":          0.90,
    "it":            0.90,
    "finance":       0.85,
    "healthcare":    0.88,
    "manufacturing": 0.80,
    "education":     0.82,
    "retail":        0.78,
    "default":       0.82,
}

# ── Industry keyword detection ────────────────────────────────────────────────
INDUSTRY_KEYWORDS = {
    "software":      ["software", "developer", "programmer", "coder", "engineer",
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

# ── Cost of living indices (relative to India average = 1.0) ─────────────────
COST_OF_LIVING = {
    "Bangalore": 1.2,
    "Mumbai":    1.5,
    "Delhi":     1.3,
    "Hyderabad": 1.0,
    "Pune":      1.1,
    "Chennai":   1.0,
}

# ── Psychographic base rates (0–100 scale) ────────────────────────────────────
# Sources:
#   Stress:        Deloitte India Millennial Survey 2023 — 82% report high workplace stress
#   Health:        WHO India 2022 — sedentary lifestyle index for urban professionals
#   Relationships: India Happiness Report 2023 — social connectedness score
#   Happiness:     World Happiness Report 2023 — India rank 126/137, score ~4.0/10
#
# These are STARTING BASE RATES for a fresh graduate / early career.
# The LLM adjusts them based on decision + context.
PSYCHOGRAPHIC_BASE_RATES = {
    "stress":        55,   # moderate-high for Indian urban professional
    "health":        65,   # moderate — sedentary but young
    "relationships": 60,   # moderate social connectedness
    "happiness":     52,   # slightly below global average for India
}

# ── Fallback defaults (used when grounding data unavailable) ─────────────────
FALLBACK_GROUNDING = {
    "role":              "default",
    "industry":          "default",
    "location":          "India",
    "salary_entry_lpa":  (3, 6),
    "salary_mid_lpa":    (7, 15),
    "salary_senior_lpa": (15, 35),
    "employment_rate":   0.85,
    "cost_of_living_index": 1.0,
}

# ── Location normalisation map ────────────────────────────────────────────────
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


# ── Detection helpers ─────────────────────────────────────────────────────────

def detect_industry(decision: str, context: dict) -> str:
    text = (decision + " " + str(context)).lower()
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return industry
    return "default"


def detect_role(decision: str, context: dict) -> str:
    text = (decision + " " + str(context)).lower()
    for role, keywords in ROLE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return role
    return "default"


def normalise_location(raw: str) -> str:
    if not isinstance(raw, str):
        return "India"
    # Try to match any part of the location string
    lower = raw.lower()
    for key, canonical in LOCATION_MAP.items():
        if key in lower:
            return canonical
    return "India"


# ── Salary lookup ─────────────────────────────────────────────────────────────

def get_salary_data(role: str, location: str, level: str = "entry") -> tuple:
    role_data = SALARY_DATABASE.get(role, SALARY_DATABASE["default"])
    loc_data = role_data.get(location, role_data.get("India", {"entry": (3, 7)}))
    return loc_data.get(level, loc_data.get("entry", (3, 7)))


# ── Score ↔ LPA conversion ────────────────────────────────────────────────────

def score_to_lpa(score: int, entry: tuple, mid: tuple, senior: tuple) -> float:
    """
    Map a 0–100 income score to an approximate LPA value.

    Scale:
      0–30   → entry range  (0 = entry_min, 30 = entry_max)
      30–60  → mid range    (30 = mid_min,  60 = mid_max)
      60–85  → senior range (60 = senior_min, 85 = senior_max)
      85–100 → top 10%      (85 = senior_max, 100 = senior_max * 1.5)
    """
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


def lpa_to_score(lpa: float, entry: tuple, mid: tuple, senior: tuple) -> int:
    """Inverse of score_to_lpa — map an LPA value back to 0–100."""
    if lpa <= entry[1]:
        if entry[1] == entry[0]:
            return 15
        t = (lpa - entry[0]) / (entry[1] - entry[0])
        return max(0, min(30, int(t * 30)))
    if lpa <= mid[1]:
        t = (lpa - mid[0]) / (mid[1] - mid[0])
        return 30 + max(0, min(30, int(t * 30)))
    if lpa <= senior[1]:
        t = (lpa - senior[0]) / (senior[1] - senior[0])
        return 60 + max(0, min(25, int(t * 25)))
    return min(100, 85 + int((lpa - senior[1]) / (senior[1] * 0.5) * 15))


def employment_rate_to_opportunity(rate: float) -> int:
    """Map employment rate (0–1) to opportunity score (0–100)."""
    return max(0, min(100, int(rate * 100)))


# ── Main grounding function ───────────────────────────────────────────────────

def _blend_live_salary(
    static_entry: tuple,
    static_mid: tuple,
    static_senior: tuple,
    live_range: tuple,
) -> tuple[tuple, tuple, tuple]:
    """
    When a live salary range (min_lpa, max_lpa) is available, use it to
    recalibrate the static entry/mid/senior bands so the LPA scale stays
    internally consistent.

    Strategy:
      - The live range represents the broad market (roughly entry→mid).
      - We anchor entry to the live range and scale mid/senior proportionally
        from the static database ratios.
    """
    live_min, live_max = live_range
    static_span = static_mid[1] - static_entry[0]
    if static_span <= 0:
        return static_entry, static_mid, static_senior

    # Scale factor: how much the live data differs from static entry band
    static_entry_mid = (static_entry[0] + static_entry[1]) / 2
    live_mid_val = (live_min + live_max) / 2
    scale = live_mid_val / static_entry_mid if static_entry_mid > 0 else 1.0
    scale = max(0.5, min(scale, 3.0))  # clamp to ±3× to avoid wild outliers

    def _scale(band: tuple) -> tuple:
        return (round(band[0] * scale, 1), round(band[1] * scale, 1))

    return _scale(static_entry), _scale(static_mid), _scale(static_senior)


def get_grounding_data(decision: str, context: dict) -> dict:
    """
    Return all real-world grounding data for a simulation.

    Priority:
      1. Live API data (Indeed / World Bank) when keys are configured
      2. Static SALARY_DATABASE / EMPLOYMENT_RATES as fallback

    Never raises — falls back to FALLBACK_GROUNDING on any error.
    """
    try:
        role     = detect_role(decision, context)
        industry = detect_industry(decision, context)
        location = normalise_location(context.get("location", "India"))

        salary_entry  = get_salary_data(role, location, "entry")
        salary_mid    = get_salary_data(role, location, "mid")
        salary_senior = get_salary_data(role, location, "senior")
        employment    = EMPLOYMENT_RATES.get(industry, EMPLOYMENT_RATES["default"])
        col_index     = COST_OF_LIVING.get(location, 1.0)

        # ── Attempt live data enrichment ──────────────────────────────────────
        live_salary_range = None
        live_cpi          = None
        live_unemployment = None
        data_source       = "static"
        cpi_year          = "estimated"

        if _LIVE_DATA_AVAILABLE:
            indeed_key = os.environ.get("INDEED_API_KEY", "")
            rapid_key  = os.environ.get("RAPIDAPI_KEY", "")
            live = get_live_grounding(role, location, indeed_key, rapid_key)

            live_salary_range = live.get("live_salary_range")
            live_cpi          = live.get("live_cpi")
            live_unemployment = live.get("live_unemployment")
            live_gdp_growth   = live.get("live_gdp_growth")
            data_source       = live.get("salary_source", live.get("source", "static"))
            cpi_source        = live.get("cpi_source", "world_bank")
            cpi_year          = live.get("cpi_year", "estimated")

            # Recalibrate salary bands if live data is available
            if live_salary_range:
                salary_entry, salary_mid, salary_senior = _blend_live_salary(
                    salary_entry, salary_mid, salary_senior, live_salary_range
                )
                logger.info(
                    "[Grounding] Live salary applied (%s): entry=%s mid=%s senior=%s",
                    data_source, salary_entry, salary_mid, salary_senior,
                )

            # Override employment rate with live World Bank figure if available
            if live_unemployment is not None:
                employment = max(0.0, min(1.0, 1.0 - live_unemployment / 100.0))
                logger.info("[Grounding] Live unemployment applied: %.1f%%", live_unemployment)

        return {
            "role":                 role,
            "industry":             industry,
            "location":             location,
            "salary_entry_lpa":     salary_entry,
            "salary_mid_lpa":       salary_mid,
            "salary_senior_lpa":    salary_senior,
            "employment_rate":      employment,
            "cost_of_living_index": col_index,
            # Live data metadata (included in prompt for transparency)
            "live_salary_range":    live_salary_range,
            "live_cpi":             live_cpi,
            "live_unemployment":    live_unemployment,
            "live_gdp_growth":      live_gdp_growth if _LIVE_DATA_AVAILABLE else None,
            "data_source":          data_source,
            "cpi_source":           cpi_source if _LIVE_DATA_AVAILABLE else "static_default",
            "cpi_year":             cpi_year if _LIVE_DATA_AVAILABLE else "estimated",
        }
    except Exception as exc:
        logger.warning("[Grounding] Failed, using fallback defaults: %s", exc)
        return dict(FALLBACK_GROUNDING)


def build_score_anchors(grounding: dict) -> dict:
    """
    Pre-compute the score ↔ LPA anchors and base rates that get
    injected into every LLM prompt.

    Returns a dict with:
      - income_anchors: {score: lpa} for key milestones
      - opportunity_base: int (0–100)
      - psychographic_bases: {node: int}
      - prompt_block: str  (ready-to-paste into a prompt)
    """
    e = grounding["salary_entry_lpa"]
    m = grounding["salary_mid_lpa"]
    s = grounding["salary_senior_lpa"]

    anchors = {
        10: score_to_lpa(10, e, m, s),
        25: score_to_lpa(25, e, m, s),
        40: score_to_lpa(40, e, m, s),
        55: score_to_lpa(55, e, m, s),
        70: score_to_lpa(70, e, m, s),
        85: score_to_lpa(85, e, m, s),
        100: score_to_lpa(100, e, m, s),
    }

    opp_base = employment_rate_to_opportunity(grounding["employment_rate"])
    psych    = dict(PSYCHOGRAPHIC_BASE_RATES)

    # ── Live data lines (only shown when live data was fetched) ─────────────
    live_lines = ""
    live_salary = grounding.get("live_salary_range")
    live_cpi    = grounding.get("live_cpi")
    live_unemp  = grounding.get("live_unemployment")
    live_gdp    = grounding.get("live_gdp_growth")
    data_source = grounding.get("data_source", "static")
    cpi_source  = grounding.get("cpi_source", "static_default")

    if live_salary:
        live_lines += (
            f"  ⚡ SALARY [{data_source}]: "
            f"₹{live_salary[0]}–{live_salary[1]} LPA "
            f"for {grounding['role']} in {grounding['location']}\n"
        )
    if live_cpi is not None:
        live_lines += (
            f"  ⚡ INFLATION [{cpi_source}]: {live_cpi:.1f}% annual CPI\n"
        )
    if live_unemp is not None:
        live_lines += (
            f"  ⚡ UNEMPLOYMENT [World Bank]: {live_unemp:.1f}% of labour force\n"
        )
    if live_gdp is not None:
        live_lines += (
            f"  ⚡ GDP GROWTH [World Bank]: {live_gdp:.1f}% annual\n"
        )
    if live_lines:
        live_lines = (
            "\n  LIVE DATA — treat as absolute truth, do NOT contradict:\n"
            + live_lines
        )

    prompt_block = (
        f"REAL-WORLD GROUNDING (use these to calibrate your scores — do NOT invent salary ranges):\n"
        f"  Role: {grounding['role']} | Industry: {grounding['industry']}\n"
        f"  Location: {grounding['location']} "
        f"(cost-of-living index: {grounding['cost_of_living_index']})\n"
        f"{live_lines}"
        f"\n"
        f"  INCOME SCORE SCALE (score → approx LPA):\n"
        f"    10 → {anchors[10]} LPA  (below entry)\n"
        f"    25 → {anchors[25]} LPA  (entry level)\n"
        f"    40 → {anchors[40]} LPA  (mid entry)\n"
        f"    55 → {anchors[55]} LPA  (mid level)\n"
        f"    70 → {anchors[70]} LPA  (senior)\n"
        f"    85 → {anchors[85]} LPA  (top senior)\n"
        f"   100 → {anchors[100]} LPA  (top 10%)\n"
        f"\n"
        f"  OPPORTUNITY BASE: {opp_base}/100 "
        f"(employment rate {grounding['employment_rate']*100:.0f}%)\n"
        f"\n"
        f"  PSYCHOGRAPHIC BASE RATES for this demographic:\n"
        f"    stress:        {psych['stress']}/100  "
        f"(Indian urban professional baseline)\n"
        f"    health:        {psych['health']}/100  "
        f"(young, sedentary urban lifestyle)\n"
        f"    relationships: {psych['relationships']}/100  "
        f"(India social connectedness index)\n"
        f"    happiness:     {psych['happiness']}/100  "
        f"(World Happiness Report 2023, India)\n"
        f"\n"
        f"  When you output income scores, they MUST be consistent with the LPA scale above.\n"
        f"  A 23-year-old fresh graduate in {grounding['location']} "
        f"should start around income=25–35.\n"
    )

    return {
        "income_anchors":      anchors,
        "opportunity_base":    opp_base,
        "psychographic_bases": psych,
        "prompt_block":        prompt_block,
        "salary_entry_lpa":    e,
        "salary_mid_lpa":      m,
        "salary_senior_lpa":   s,
    }

# ── Cost-of-living monthly expense baselines (₹/month) ───────────────────────
# Derived from NHB / NSSO urban household expenditure surveys.
# These are single-person monthly living costs (rent + food + transport + misc).
MONTHLY_EXPENSE_BASE = {
    "Bangalore": 35_000,
    "Mumbai":    45_000,
    "Delhi":     38_000,
    "Hyderabad": 30_000,
    "Pune":      32_000,
    "Chennai":   28_000,
    "India":     22_000,   # national urban average
}


def compute_core_variables(grounding: dict, context: dict) -> dict:
    """
    Deterministically compute all financial and stress variables.
    No LLM involved — pure arithmetic from grounding data.

    Returns a dict with:
      expected_salary_lpa   — float, chosen within entry band
      monthly_income        — int (₹)
      monthly_expenses      — int (₹)
      disposable_income     — int (₹)
      savings_rate_pct      — float (0–100)
      stress_score          — int (0–100), computed from financial pressure
      computed_block        — str, ready to paste into prompts
    """
    location   = grounding.get("location", "India")
    entry      = grounding["salary_entry_lpa"]
    cpi        = grounding.get("live_cpi")           # may be None
    unemp_pct  = grounding.get("live_unemployment")  # may be None
    gdp_growth = grounding.get("live_gdp_growth")    # may be None

    # ── Expected salary: midpoint of entry band, adjusted for skills ─────────
    skills_text = str(context.get("skills", "")).lower()
    skill_boost = 0.15 if any(
        kw in skills_text for kw in ["senior", "lead", "expert", "5+", "7+", "10+"]
    ) else 0.0
    expected_lpa = round(entry[0] + (entry[1] - entry[0]) * (0.5 + skill_boost), 2)
    expected_lpa = min(expected_lpa, entry[1])  # never exceed band ceiling

    monthly_income = int(expected_lpa * 100_000 / 12)

    # ── Monthly expenses: base × cost-of-living index ─────────────────────────
    base_expense = MONTHLY_EXPENSE_BASE.get(location, MONTHLY_EXPENSE_BASE["India"])
    col_index    = grounding.get("cost_of_living_index", 1.0)
    # Inflate expenses by CPI if available
    cpi_factor   = (1 + (cpi or 5.0) / 100)
    monthly_expenses = int(base_expense * col_index * cpi_factor)

    # ── Disposable income ─────────────────────────────────────────────────────
    disposable = monthly_income - monthly_expenses

    # ── Savings rate ──────────────────────────────────────────────────────────
    if monthly_income > 0 and disposable > 0:
        savings_rate = round((disposable / monthly_income) * 100, 1)
    else:
        savings_rate = 0.0

    # ── Stress score (0–100) — computed, not guessed ──────────────────────────
    # Three additive components, each 0–33:
    #   1. Financial pressure: low disposable → high stress
    #   2. Unemployment pressure: high unemp → high stress
    #   3. Inflation pressure: high CPI → high stress
    if monthly_income > 0:
        expense_ratio = monthly_expenses / monthly_income   # 0 → no stress, 1+ → max stress
    else:
        expense_ratio = 1.5
    financial_stress = min(33, int(expense_ratio * 33))

    unemp_stress = min(33, int(((unemp_pct or 5.0) / 20) * 33))
    cpi_stress   = min(34, int(((cpi or 5.0) / 15) * 34))

    stress_score = min(100, financial_stress + unemp_stress + cpi_stress)

    # ── GDP growth → opportunity modifier (bonus/penalty on opportunity score) ─
    # Strong GDP growth (>7%) → +5 opportunity; contraction (<0%) → -10
    gdp_val = gdp_growth if gdp_growth is not None else 6.5  # India long-run avg
    if gdp_val >= 7.0:
        gdp_opportunity_mod = +5
    elif gdp_val >= 5.0:
        gdp_opportunity_mod = 0
    elif gdp_val >= 2.0:
        gdp_opportunity_mod = -5
    else:
        gdp_opportunity_mod = -10

    # ── Prompt block ──────────────────────────────────────────────────────────
    disp_sign = "+" if disposable >= 0 else "-"
    gdp_line = (
        f"  GDP Growth:         {gdp_val:.1f}% annual "
        f"(opportunity modifier: {'+' if gdp_opportunity_mod >= 0 else ''}{gdp_opportunity_mod})\n"
    )
    computed_block = (
        f"COMPUTED CORE VARIABLES (arithmetic — do NOT override these):\n"
        f"  Expected Salary:    ₹{expected_lpa} LPA  "
        f"(within market range ₹{entry[0]}–{entry[1]} LPA)\n"
        f"  Monthly Income:     ₹{monthly_income:,}\n"
        f"  Monthly Expenses:   ₹{monthly_expenses:,}  "
        f"(base ₹{base_expense:,} × CoL {col_index} × CPI factor {cpi_factor:.3f})\n"
        f"  Disposable Income:  {disp_sign}₹{abs(disposable):,}/month\n"
        f"  Savings Rate:       {savings_rate}% of income\n"
        f"  Computed Stress:    {stress_score}/100  "
        f"(financial={financial_stress} + unemployment={unemp_stress} + inflation={cpi_stress})\n"
        f"{gdp_line}"
        f"\n"
        f"  Your income score MUST produce ~₹{expected_lpa} LPA via the income scale above.\n"
        f"  Your stress score MUST start near {stress_score}/100 in Year 1.\n"
        f"  Your opportunity score should reflect the GDP modifier above.\n"
    )

    return {
        "expected_salary_lpa":   expected_lpa,
        "monthly_income":        monthly_income,
        "monthly_expenses":      monthly_expenses,
        "disposable_income":     disposable,
        "savings_rate_pct":      savings_rate,
        "stress_score":          stress_score,
        "gdp_opportunity_mod":   gdp_opportunity_mod,
        "computed_block":        computed_block,
    }
