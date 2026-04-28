"""
Real-time data provider — official, open, and reliable sources only.

Priority chain:
  Salary  : AmbitionBox (scrape) → Indeed Scraper API → OpenWeb Ninja → static DB
  CPI     : World Bank Open Data → static default (5.5%)
  Macro   : World Bank Open Data (unemployment, labour force, GDP growth)

All results are cached in-memory for 24 hours to minimise network calls.
Every fetch degrades silently to None so callers can fall back to the
static SALARY_DATABASE in data_grounding.py.
"""
import re
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Cache ─────────────────────────────────────────────────────────────────────
_cache: dict = {}
_TTL = timedelta(hours=24)

def _cached(key: str):
    entry = _cache.get(key)
    if entry and datetime.now() - entry[0] < _TTL:
        return entry[1]
    return None

def _store(key: str, value):
    _cache[key] = (datetime.now(), value)
    return value


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 1 — AmbitionBox  (public salary pages, no API key required)
# ─────────────────────────────────────────────────────────────────────────────

# Role → AmbitionBox URL slug mapping
_AMBITIONBOX_SLUGS = {
    "software engineer":   "software-engineer",
    "data scientist":      "data-scientist",
    "product manager":     "product-manager",
    "mechanical engineer": "mechanical-engineer",
    "designer":            "designer",
    "default":             "software-engineer",
}

# City → AmbitionBox city filter slug
_AMBITIONBOX_CITIES = {
    "Bangalore": "bangalore",
    "Mumbai":    "mumbai",
    "Delhi":     "delhi",
    "Hyderabad": "hyderabad",
    "Pune":      "pune",
    "Chennai":   "chennai",
}

def _ambitionbox_url(role: str, location: str) -> str:
    slug = _AMBITIONBOX_SLUGS.get(role, _AMBITIONBOX_SLUGS["default"])
    city = _AMBITIONBOX_CITIES.get(location, "")
    base = f"https://www.ambitionbox.com/profile/{slug}-salary"
    return f"{base}?city={city}" if city else base

def _parse_lpa(text: str) -> Optional[float]:
    """Extract a single LPA float from strings like '9.5 Lakhs' or '₹9,50,000'."""
    # Match patterns like "9.5 Lakhs", "9 LPA", "9,50,000"
    m = re.search(r"([\d]+\.?[\d]*)\s*(?:lakh|lpa|l\.p\.a)", text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    # Fallback: raw rupee amount ≥ 1,00,000
    nums = re.findall(r"[\d,]+", text)
    for n in nums:
        val = int(n.replace(",", ""))
        if val >= 100_000:
            return round(val / 100_000, 1)
    return None

def get_ambitionbox_salary(role: str, location: str) -> Optional[tuple]:
    """
    Scrape AmbitionBox public salary page for a role+city.
    Returns (min_lpa, max_lpa) or None.
    No API key required — public HTML page.
    """
    key = f"ambitionbox_{role.lower()}_{location.lower()}"
    cached = _cached(key)
    if cached is not None:
        logger.debug("[RealData] AmbitionBox cache hit: %s", key)
        return cached

    url = _ambitionbox_url(role, location)
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-IN,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code != 200:
            logger.warning("[RealData] AmbitionBox HTTP %s for %s", resp.status_code, url)
            return None

        html = resp.text

        # Pattern 1: "₹ 8.9 Lakhs to ₹ 9.8 Lakhs" (AmbitionBox standard format)
        range_match = re.search(
            r"₹\s*([\d]+\.?[\d]*)\s*Lakhs?\s+to\s+₹\s*([\d]+\.?[\d]*)\s*Lakhs?",
            html, re.IGNORECASE
        )
        if range_match:
            lo = float(range_match.group(1))
            hi = float(range_match.group(2))
            if 1 <= lo <= hi <= 500:
                result = (round(lo, 1), round(hi, 1))
                logger.info("[RealData] AmbitionBox salary %s in %s: %s LPA", role, location, result)
                return _store(key, result)

        # Pattern 2: "X - Y Lakhs" or "X – Y LPA"
        range_match = re.search(
            r"([\d]+\.?[\d]*)\s*[-–]\s*([\d]+\.?[\d]*)\s*(?:lakhs?|lpa|l\.p\.a)",
            html, re.IGNORECASE
        )
        if range_match:
            lo = float(range_match.group(1))
            hi = float(range_match.group(2))
            if 1 <= lo <= hi <= 500:
                result = (round(lo, 1), round(hi, 1))
                logger.info("[RealData] AmbitionBox salary %s in %s: %s LPA", role, location, result)
                return _store(key, result)

        # Pattern 3: single average "average annual salary of ₹ X Lakhs" → ±20% range
        avg_match = re.search(
            r"average\s+(?:annual\s+)?salary\s+of\s+₹\s*([\d]+\.?[\d]*)\s*Lakhs?",
            html, re.IGNORECASE
        )
        if avg_match:
            avg = float(avg_match.group(1))
            result = (round(avg * 0.8, 1), round(avg * 1.2, 1))
            logger.info("[RealData] AmbitionBox avg salary %s in %s: %s LPA", role, location, result)
            return _store(key, result)

    except Exception as exc:
        logger.warning("[RealData] AmbitionBox fetch failed: %s", exc)

    return None



# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 2 — World Bank Open Data  (no API key, unlimited)
# ─────────────────────────────────────────────────────────────────────────────

# World Bank indicator codes for India
_WB_INDICATORS = {
    "unemployment":    "SL.UEM.TOTL.ZS",    # Unemployment, total (% labour force)
    "cpi":             "FP.CPI.TOTL.ZG",    # Inflation, consumer prices (annual %)
    "gdp_growth":      "NY.GDP.MKTP.KD.ZG", # GDP growth (annual %)
    "labour_force":    "SL.TLF.TOTL.IN",    # Labour force, total
}


def get_cpi_world_bank() -> dict:
    """
    Fetch latest CPI (inflation %) for India from World Bank Open Data.
    Returns {"cpi": float, "year": str, "source": str} always — never raises.
    """
    key = "wb_cpi_structured"
    cached = _cached(key)
    if cached is not None:
        return cached

    try:
        url = (
            "https://api.worldbank.org/v2/country/IN/indicator/"
            "FP.CPI.TOTL.ZG?format=json"
        )
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            raise Exception(f"World Bank API returned HTTP {resp.status_code}")

        data = resp.json()
        if not data or len(data) < 2:
            raise Exception("Invalid response format")

        for entry in data[1]:
            if entry.get("value") is not None:
                result = {
                    "cpi":    round(float(entry["value"]), 2),
                    "year":   entry["date"],
                    "source": "world_bank",
                }
                logger.info(
                    "[RealData] World Bank CPI (India %s): %.2f%%",
                    result["year"], result["cpi"],
                )
                return _store(key, result)

        raise Exception("No valid CPI data found in response")

    except Exception as exc:
        logger.warning("[RealData] World Bank CPI failed: %s — using fallback", exc)
        return {"cpi": 5.5, "year": "estimated", "source": "fallback"}


def _worldbank_fetch(indicator: str) -> Optional[float]:
    """Fetch the most recent value for a World Bank indicator for India."""
    key = f"wb_{indicator}"
    cached = _cached(key)
    if cached is not None:
        return cached

    code = _WB_INDICATORS.get(indicator)
    if not code:
        return None

    url = f"https://api.worldbank.org/v2/country/IN/indicator/{code}"
    try:
        resp = requests.get(
            url,
            params={"format": "json", "mrv": 3, "per_page": 3},
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, list) and len(payload) > 1:
            # Walk records newest-first, take first non-null value
            for record in payload[1]:
                val = record.get("value")
                if val is not None:
                    result = float(val)
                    logger.info("[RealData] World Bank %s (India): %.3f", indicator, result)
                    return _store(key, result)
    except Exception as exc:
        logger.warning("[RealData] World Bank %s fetch failed: %s", indicator, exc)
    return None

def get_worldbank_unemployment() -> Optional[float]:
    return _worldbank_fetch("unemployment")

def get_worldbank_cpi() -> Optional[float]:
    return _worldbank_fetch("cpi")

def get_worldbank_gdp_growth() -> Optional[float]:
    return _worldbank_fetch("gdp_growth")


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 4 — Indeed Scraper API  (5,000 free req/month, key required)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_salary_snippet(snippet: str) -> Optional[tuple]:
    """Extract (min_lpa, max_lpa) from '₹8,00,000 - ₹14,00,000 a year'."""
    numbers = re.findall(r"[\d,]+", snippet)
    cleaned = [int(n.replace(",", "")) for n in numbers if len(n.replace(",", "")) >= 4]
    if len(cleaned) >= 2:
        return (round(cleaned[0] / 100_000, 1), round(cleaned[1] / 100_000, 1))
    if len(cleaned) == 1:
        lpa = round(cleaned[0] / 100_000, 1)
        return (lpa, lpa)
    return None

def get_indeed_salary(role: str, location: str, api_key: str) -> Optional[tuple]:
    """Fetch salary range from Indeed Scraper API. Returns (min_lpa, max_lpa) or None."""
    if not api_key:
        return None

    key = f"indeed_{role.lower()}_{location.lower()}"
    cached = _cached(key)
    if cached is not None:
        return cached

    try:
        resp = requests.get(
            "https://indeed-scraper.omkar.cloud/indeed/search",
            headers={"API-Key": api_key},
            params={"search_term": role, "location": location, "country": "in"},
            timeout=10,
        )
        resp.raise_for_status()
        jobs = resp.json()
        if not isinstance(jobs, list) or not jobs:
            return None

        salaries = []
        for job in jobs[:10]:
            snippet = job.get("salary_snippet") or job.get("salary") or ""
            parsed = _parse_salary_snippet(str(snippet))
            if parsed:
                salaries.append(parsed)

        if not salaries:
            return None

        avg_min = round(sum(s[0] for s in salaries) / len(salaries), 1)
        avg_max = round(sum(s[1] for s in salaries) / len(salaries), 1)
        result = (avg_min, avg_max)
        logger.info("[RealData] Indeed salary %s in %s: %s LPA", role, location, result)
        return _store(key, result)

    except Exception as exc:
        logger.warning("[RealData] Indeed salary fetch failed: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 5 — OpenWeb Ninja via RapidAPI  (50 free req/month, key required)
# ─────────────────────────────────────────────────────────────────────────────

def get_openweb_salary(role: str, location: str, rapid_api_key: str) -> Optional[tuple]:
    """Fetch salary from OpenWeb Ninja Job Salary API. Returns (min_lpa, max_lpa) or None."""
    if not rapid_api_key:
        return None

    key = f"openweb_{role.lower()}_{location.lower()}"
    cached = _cached(key)
    if cached is not None:
        return cached

    try:
        resp = requests.get(
            "https://job-salary-data.p.rapidapi.com/job-salary",
            headers={
                "X-RapidAPI-Key": rapid_api_key,
                "X-RapidAPI-Host": "job-salary-data.p.rapidapi.com",
            },
            params={"job_title": role, "location": location, "radius": "100"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        min_sal = data.get("min_salary")
        max_sal = data.get("max_salary")
        if min_sal and max_sal:
            # API returns annual USD — convert to LPA (1 USD ≈ 83 INR)
            min_lpa = round(float(min_sal) * 83 / 100_000, 1)
            max_lpa = round(float(max_sal) * 83 / 100_000, 1)
            result = (min_lpa, max_lpa)
            logger.info("[RealData] OpenWeb salary %s in %s: %s LPA", role, location, result)
            return _store(key, result)
    except Exception as exc:
        logger.warning("[RealData] OpenWeb Ninja fetch failed: %s", exc)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Composite fetch — called by data_grounding.get_grounding_data()
# ─────────────────────────────────────────────────────────────────────────────

def get_live_grounding(
    role: str,
    location: str,
    indeed_api_key: str = "",
    rapid_api_key: str = "",
) -> dict:
    """
    Fetch all live grounding data for a role/location.

    Salary priority  : AmbitionBox → Indeed → OpenWeb Ninja → None (static fallback)
    CPI priority     : World Bank Open Data → static default (5.5%)
    Macro indicators : World Bank (unemployment, GDP growth)

    Returns:
      live_salary_range  — (min_lpa, max_lpa) or None
      live_cpi           — float % (always set, never None)
      live_unemployment  — float % or None
      live_gdp_growth    — float % or None
      salary_source      — which source provided the salary
      cpi_source         — which source provided CPI
    """
    # ── Salary ────────────────────────────────────────────────────────────────
    salary = get_ambitionbox_salary(role, location)
    salary_source = "ambitionbox"

    if salary is None:
        salary = get_indeed_salary(role, location, indeed_api_key)
        salary_source = "indeed"

    if salary is None and rapid_api_key:
        salary = get_openweb_salary(role, location, rapid_api_key)
        salary_source = "openweb_ninja"

    if salary is None:
        salary_source = "static_fallback"

    # ── CPI ───────────────────────────────────────────────────────────────────
    cpi_data   = get_cpi_world_bank()
    cpi        = cpi_data["cpi"]
    cpi_source = cpi_data["source"]
    cpi_year   = cpi_data["year"]

    # ── Macro ─────────────────────────────────────────────────────────────────
    unemployment = get_worldbank_unemployment()
    gdp_growth   = get_worldbank_gdp_growth()

    return {
        "live_salary_range": salary,
        "live_cpi":          cpi,
        "live_unemployment": unemployment,
        "live_gdp_growth":   gdp_growth,
        "salary_source":     salary_source,
        "cpi_source":        cpi_source,
        "cpi_year":          cpi_year,
        # legacy key kept for backward compat
        "source":            salary_source,
    }
