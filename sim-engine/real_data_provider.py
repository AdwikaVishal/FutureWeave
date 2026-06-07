import asyncio
import re
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_cache: dict = {}
_TTL = timedelta(hours=24)


def _cached(key: str):
    entry = _cache.get(key)
    if entry and datetime.now(timezone.utc) - entry[0] < _TTL:
        return entry[1]
    return None


def _store(key: str, value):
    _cache[key] = (datetime.now(timezone.utc), value)
    return value


def _run_sync(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()


_AMBITIONBOX_SLUGS = {
    "software engineer":   "software-engineer",
    "data scientist":      "data-scientist",
    "product manager":     "product-manager",
    "mechanical engineer": "mechanical-engineer",
    "designer":            "designer",
    "default":             "software-engineer",
}

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
    m = re.search(r"([\d]+\.?[\d]*)\s*(?:lakh|lpa|l\.p\.a)", text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    nums = re.findall(r"[\d,]+", text)
    for n in nums:
        val = int(n.replace(",", ""))
        if val >= 100_000:
            return round(val / 100_000, 1)
    return None


WB_INDICATORS = {
    "unemployment":    "SL.UEM.TOTL.ZS",
    "cpi":             "FP.CPI.TOTL.ZG",
    "gdp_growth":      "NY.GDP.MKTP.KD.ZG",
    "labour_force":    "SL.TLF.TOTL.IN",
}


def get_cpi_world_bank() -> dict:
    key = "wb_cpi_structured"
    cached = _cached(key)
    if cached is not None:
        return cached

    try:
        import requests
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
                    "is_historical": True,
                }
                logger.info(
                    "[LIVE_DATA] Source=WorldBank Status=200 CPI=%.2f%% Year=%s (HISTORICAL)",
                    result["cpi"], result["year"],
                )
                return _store(key, result)

        raise Exception("No valid CPI data found in response")

    except Exception as exc:
        logger.warning("[LIVE_DATA] Source=WorldBank Status=ERROR CPI fetch failed: %s", exc)
        return {
            "cpi": None,
            "year": None,
            "source": "failed",
            "error": str(exc),
            "is_historical": True,
        }


def _worldbank_fetch(indicator: str) -> Optional[float]:
    key = f"wb_{indicator}"
    cached = _cached(key)
    if cached is not None:
        return cached

    code = WB_INDICATORS.get(indicator)
    if not code:
        return None

    url = f"https://api.worldbank.org/v2/country/IN/indicator/{code}"
    try:
        import requests
        resp = requests.get(
            url,
            params={"format": "json", "mrv": 3, "per_page": 3},
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, list) and len(payload) > 1:
            for record in payload[1]:
                val = record.get("value")
                if val is not None:
                    result = float(val)
                    logger.info("[LIVE_DATA] Source=WorldBank Status=200 %s=%.3f (HISTORICAL)", indicator, result)
                    return _store(key, result)
    except Exception as exc:
        logger.warning("[LIVE_DATA] Source=WorldBank Status=ERROR %s fetch failed: %s", indicator, exc)
    return None


def get_worldbank_unemployment() -> Optional[float]:
    return _worldbank_fetch("unemployment")


def get_worldbank_cpi() -> Optional[float]:
    return _worldbank_fetch("cpi")


def get_worldbank_gdp_growth() -> Optional[float]:
    return _worldbank_fetch("gdp_growth")


def _parse_salary_snippet(snippet: str) -> Optional[tuple]:
    numbers = re.findall(r"[\d,]+", snippet)
    cleaned = [int(n.replace(",", "")) for n in numbers if len(n.replace(",", "")) >= 4]
    if len(cleaned) >= 2:
        return (round(cleaned[0] / 100_000, 1), round(cleaned[1] / 100_000, 1))
    if len(cleaned) == 1:
        lpa = round(cleaned[0] / 100_000, 1)
        return (lpa, lpa)
    return None


def get_indeed_salary(role: str, location: str, api_key: str) -> Optional[tuple]:
    if not api_key:
        return None

    key = f"indeed_{role.lower()}_{location.lower()}"
    cached = _cached(key)
    if cached is not None:
        return cached

    try:
        import requests
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
        logger.info("[LIVE_DATA] Source=Indeed Status=200 %s in %s: %s LPA", role, location, result)
        return _store(key, result)

    except Exception as exc:
        logger.warning("[LIVE_DATA] Source=Indeed Status=ERROR fetch failed: %s", exc)
        return None


def get_openweb_salary(role: str, location: str, rapid_api_key: str) -> Optional[tuple]:
    if not rapid_api_key:
        return None

    key = f"openweb_{role.lower()}_{location.lower()}"
    cached = _cached(key)
    if cached is not None:
        return cached

    try:
        import requests
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
            min_lpa = round(float(min_sal) * 83 / 100_000, 1)
            max_lpa = round(float(max_sal) * 83 / 100_000, 1)
            result = (min_lpa, max_lpa)
            logger.info("[LIVE_DATA] Source=OpenWeb Status=200 %s in %s: %s LPA", role, location, result)
            return _store(key, result)
    except Exception as exc:
        logger.warning("[LIVE_DATA] Source=OpenWeb Status=ERROR fetch failed: %s", exc)
    return None


def get_live_grounding(
    role: str,
    location: str,
    indeed_api_key: str = "",
    rapid_api_key: str = "",
) -> dict:
    salary = None
    salary_source = "unavailable"

    cpi_data = get_cpi_world_bank()
    cpi = cpi_data.get("cpi")
    cpi_source = cpi_data.get("source", "unavailable")
    cpi_year = cpi_data.get("year")

    unemployment = get_worldbank_unemployment()
    gdp_growth = get_worldbank_gdp_growth()

    try:
        from services.ambitionbox import fetch_salary
        pr = _run_sync(fetch_salary(role, location))
        if pr and pr.available:
            rng = pr.data.get("salary_range_lpa", [])
            if len(rng) >= 2:
                salary = (rng[0], rng[1])
                salary_source = pr.provider
    except Exception:
        pass

    if salary is None:
        salary = get_indeed_salary(role, location, indeed_api_key)
        if salary:
            salary_source = "indeed"

    if salary is None and rapid_api_key:
        salary = get_openweb_salary(role, location, rapid_api_key)
        if salary:
            salary_source = "openweb_ninja"

    if salary is None:
        salary_source = "unavailable"

    return {
        "live_salary_range": salary,
        "live_cpi": cpi,
        "live_unemployment": unemployment,
        "live_gdp_growth": gdp_growth,
        "salary_source": salary_source,
        "cpi_source": cpi_source,
        "cpi_year": cpi_year,
        "source": salary_source,
    }
