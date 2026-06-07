"""
IMF World Economic Outlook (WEO) service.

Uses the IMF Data API (no key required).
Fetches: GDP growth, CPI inflation, unemployment for a given country.
"""
from .common import ProviderResult, fetch_json

# IMF WEO concept codes
_CONCEPTS = {
    "gdp_growth":   "NGDP_RPCH",   # Real GDP growth (%)
    "inflation":    "PCPIPCH",      # CPI inflation (%)
    "unemployment": "LUR",          # Unemployment rate (%)
}

# IMF country ISO codes
_COUNTRY_MAP = {
    "IN": "IN",
    "US": "US",
    "GB": "GB",
}


def _extract_latest(data: dict, concept: str) -> tuple[float | None, str | None]:
    """Pull the most-recent non-null annual value from an IMF WEO response."""
    try:
        series = data.get("values", {}).get(concept, {})
        if not series:
            return None, None
        # Keys are years as strings; take the highest year with a value
        years_with_values = [
            (yr, float(v))
            for yr, v in series.items()
            if v not in (None, "", "n/a", "--")
        ]
        if not years_with_values:
            return None, None
        year, value = max(years_with_values, key=lambda x: x[0])
        return round(value, 3), str(year)
    except Exception:
        return None, None


async def fetch_imf(country: str = "IN") -> ProviderResult:
    """
    Fetch GDP growth, CPI inflation, and unemployment from the IMF WEO API.
    Returns a ProviderResult with data = {values, years, errors}.
    """
    iso = _COUNTRY_MAP.get(country, country)
    concept_ids = ",".join(_CONCEPTS.values())
    url = f"https://www.imf.org/external/datamapper/api/v1/{concept_ids}/{iso}"

    result = await fetch_json(
        "imf",
        "weo",
        url,
        params={"periods": 5},
        timeout=12,
    )

    if not result.available:
        return result

    raw = result.data
    values: dict = {}
    years: dict = {}
    errors: dict = {}

    for field, concept in _CONCEPTS.items():
        country_block = raw.get("values", {}).get(concept, {}).get(iso, {})
        # Re-pack into the shape _extract_latest expects
        val, yr = _extract_latest({"values": {concept: country_block}}, concept)
        if val is not None:
            values[field] = val
            years[field] = yr
        else:
            errors[field] = f"No recent IMF WEO value for {concept}/{iso}"

    available = bool(values)
    return ProviderResult(
        provider="imf",
        dataset="weo",
        available=available,
        source_url=url,
        data={"values": values, "years": years, "errors": errors},
        error=None if available else "; ".join(errors.values()),
        latency_ms=result.latency_ms,
        cache_hit=result.cache_hit,
    )
