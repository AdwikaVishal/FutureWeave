"""
Glassdoor salary service.

Scrapes Glassdoor's public salary-explorer pages (no private API key required).
Mirrors the pattern used in ambitionbox.py.
"""
import re

import httpx

from data_grounding import normalise_location

from .common import ProviderResult, cache

_ROLE_SLUGS = {
    "software engineer":   "software-engineer",
    "data scientist":      "data-scientist",
    "product manager":     "product-manager",
    "mechanical engineer": "mechanical-engineer",
    "designer":            "designer",
    "default":             "software-engineer",
}

_CITY_IDS = {
    # Glassdoor uses numeric location IDs for Indian cities
    "Bangalore":  "3",    # locationId for Bangalore
    "Mumbai":     "4",
    "Delhi":      "5",
    "Hyderabad":  "6",
    "Pune":       "7",
    "Chennai":    "8",
}


def _url(role: str, location: str) -> str:
    slug = _ROLE_SLUGS.get(role.lower(), _ROLE_SLUGS["default"])
    city_id = _CITY_IDS.get(normalise_location(location), "")
    base = f"https://www.glassdoor.co.in/Salaries/{slug}-salary-SRCH_KO0,{len(slug)}.htm"
    return f"{base}?locId={city_id}" if city_id else base


def _parse_salary_range(html: str) -> list[float] | None:
    # Pattern 1: "₹X.X L to ₹Y.Y L" (Glassdoor India compact format)
    m = re.search(
        r"₹\s*([\d]+\.?[\d]*)\s*L\s+to\s+₹\s*([\d]+\.?[\d]*)\s*L",
        html, re.IGNORECASE,
    )
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        if 1 <= lo <= hi <= 500:
            return [round(lo, 1), round(hi, 1)]

    # Pattern 2: "₹X,XX,XXX – ₹Y,YY,YYY per year"
    m = re.search(r"₹([\d,]+)\s*[–-]\s*₹([\d,]+)\s*per year", html, re.IGNORECASE)
    if m:
        lo = round(int(m.group(1).replace(",", "")) / 1e5, 1)
        hi = round(int(m.group(2).replace(",", "")) / 1e5, 1)
        if 1 <= lo <= hi <= 500:
            return [lo, hi]

    # Pattern 3: single median "₹X,XX,XXX /yr"
    m = re.search(r"₹([\d,]+)\s*/yr", html, re.IGNORECASE)
    if m:
        median = round(int(m.group(1).replace(",", "")) / 1e5, 1)
        if 1 <= median <= 500:
            return [round(median * 0.8, 1), round(median * 1.2, 1)]

    return None


async def fetch_glassdoor_salary(role: str, location: str) -> ProviderResult:
    url = _url(role, location)
    cache_key = f"data:glassdoor:salary:{role}:{location}"

    cached = await cache.get(cache_key)
    if cached is not None:
        return ProviderResult(
            provider="glassdoor",
            dataset="salary",
            available=True,
            data=cached,
            source_url=url,
            cache_hit=True,
        )

    headers = {
        "User-Agent": "Mozilla/5.0 FutureWeave/1.0",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

        salary_range = _parse_salary_range(response.text)
        if not salary_range:
            return ProviderResult(
                provider="glassdoor",
                dataset="salary",
                available=False,
                source_url=str(response.url),
                error="salary range not found in Glassdoor response",
            )

        data = {
            "role": role,
            "location": normalise_location(location),
            "salary_range_lpa": salary_range,
        }
        await cache.set(cache_key, data)
        return ProviderResult(
            provider="glassdoor",
            dataset="salary",
            available=True,
            data=data,
            source_url=str(response.url),
        )

    except Exception as exc:
        return ProviderResult(
            provider="glassdoor",
            dataset="salary",
            available=False,
            source_url=url,
            error=str(exc),
        )
