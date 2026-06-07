import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .common import ProviderResult, fetch_json

logger = logging.getLogger("futureweave.data")

INDICATORS = {
    "unemployment": "SL.UEM.TOTL.ZS",
    "inflation": "FP.CPI.TOTL.ZG",
    "gdp_growth": "NY.GDP.MKTP.KD.ZG",
    "labour_force": "SL.TLF.TOTL.IN",
}


def _latest_value(payload: Any) -> tuple[Optional[float], Optional[str]]:
    if not isinstance(payload, list) or len(payload) < 2:
        return None, None
    for record in payload[1]:
        value = record.get("value")
        if value is not None:
            return float(value), str(record.get("date"))
    return None, None


async def fetch_worldbank(country: str = "IN") -> ProviderResult:
    values = {}
    years = {}
    sources = {}
    errors = {}

    for name, code in INDICATORS.items():
        url = f"https://api.worldbank.org/v2/country/{country}/indicator/{code}"
        result = await fetch_json(
            "worldbank",
            name,
            url,
            params={"format": "json", "mrv": 5, "per_page": 5},
        )
        if result.available:
            value, year = _latest_value(result.data)
            if value is not None:
                values[name] = value
                years[name] = year
                sources[name] = result.source_url
            else:
                errors[name] = "no recent value in World Bank response"
        else:
            errors[name] = result.error or "request failed"

    available = bool(values)
    latest_year = max(years.values()) if years else "unknown"

    if available:
        logger.info(
            "[LIVE_DATA] Source=WorldBank Status=200 Country=%s Year=%s GDP=%.2f CPI=%.2f UNEMP=%.2f",
            country, latest_year,
            values.get("gdp_growth", -1),
            values.get("inflation", -1),
            values.get("unemployment", -1),
        )
        data_age = datetime.now(timezone.utc).year - int(latest_year) if latest_year and latest_year.isdigit() else 0
        logger.info(
            "[LIVE_DATA] Source=WorldBank Note=HISTORICAL_DATA Data is %d years old, NOT real-time",
            data_age,
        )

    return ProviderResult(
        provider="worldbank",
        dataset="macro",
        available=available,
        data={
            "values": values,
            "years": years,
            "sources": sources,
            "errors": errors,
            "is_historical": True,
            "latest_year": latest_year,
            "lag_years": datetime.now(timezone.utc).year - int(latest_year) if latest_year.isdigit() else None,
        },
        is_historical=True,
        data_year=latest_year,
        error=None if available else "; ".join(f"{k}: {v}" for k, v in errors.items()),
    )
