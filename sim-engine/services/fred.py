import os

from .common import ProviderResult, fetch_json


async def fetch_industry_data(industry: str) -> ProviderResult:
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        return ProviderResult(
            provider="fred",
            dataset="industry",
            available=False,
            error="FRED_API_KEY is not configured",
        )

    # US-oriented proxy series. Kept explicit and source-tagged instead of pretending
    # it is India-specific industry data.
    series_id = os.environ.get("FRED_INDUSTRY_SERIES_ID", "PAYEMS")
    result = await fetch_json(
        "fred",
        "industry",
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "api_key": api_key,
            "series_id": series_id,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        },
    )
    if result.available:
        observations = result.data.get("observations") or []
        if observations:
            result.data = {
                "industry": industry,
                "series_id": series_id,
                "latest": observations[0],
                "scope": "US proxy series, not India-specific",
            }
            return result
    result.available = False
    result.error = result.error or "FRED response had no observations"
    return result

