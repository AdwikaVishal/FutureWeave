"""
India Government Statistics service — MOSPI via data.gov.in.

Uses the open data.gov.in SPARQL/JSON API (no key required for public datasets).
Fetches:
  - CPI All-India (MOSPI Consumer Price Index)
  - Periodic Labour Force Survey (PLFS) unemployment proxy
"""
from .common import ProviderResult, fetch_json

# data.gov.in resource IDs for open datasets
_MOSPI_CPI_URL = (
    "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
)
_PLFS_URL = (
    "https://api.data.gov.in/resource/60aa81ad-5f0b-4c65-a9bc-a5b8b1a2b6c0"
)


def _latest_cpi(records: list) -> tuple[float | None, str | None]:
    """Extract the most recent All-India CPI value."""
    for rec in records:
        # Field names vary by dataset version; try common keys
        for key in ("value", "cpi_value", "general", "all_india"):
            raw = rec.get(key)
            if raw not in (None, "", "NA"):
                try:
                    return float(str(raw).replace(",", "")), rec.get("year") or rec.get("month_year")
                except ValueError:
                    pass
    return None, None


async def fetch_india_gov_stats() -> ProviderResult:
    """
    Fetch CPI and PLFS data from data.gov.in open APIs.
    Returns a ProviderResult with data = {cpi, cpi_year, plfs_unemployment, errors}.
    """
    cpi_result = await fetch_json(
        "india_gov",
        "mospi_cpi",
        _MOSPI_CPI_URL,
        params={"api-version": "2.0", "format": "json", "limit": 10, "sort[created_at]": "desc"},
        timeout=10,
    )

    values: dict = {}
    errors: dict = {}

    if cpi_result.available:
        records = cpi_result.data.get("records") or cpi_result.data.get("fields") or []
        cpi_val, cpi_year = _latest_cpi(records)
        if cpi_val is not None:
            values["cpi"] = cpi_val
            values["cpi_year"] = cpi_year
        else:
            errors["cpi"] = "MOSPI CPI records found but no parseable value"
    else:
        errors["cpi"] = cpi_result.error or "data.gov.in CPI request failed"

    # PLFS — best-effort only; dataset shape is less predictable
    plfs_result = await fetch_json(
        "india_gov",
        "plfs",
        _PLFS_URL,
        params={"api-version": "2.0", "format": "json", "limit": 5},
        timeout=10,
    )

    if plfs_result.available:
        records = plfs_result.data.get("records") or []
        for rec in records:
            for key in ("unemployment_rate", "ur", "cwu_rural_plus_urban"):
                raw = rec.get(key)
                if raw not in (None, "", "NA"):
                    try:
                        values["plfs_unemployment"] = float(str(raw).replace(",", ""))
                        break
                    except ValueError:
                        pass
        if "plfs_unemployment" not in values:
            errors["plfs"] = "PLFS records found but unemployment rate not parseable"
    else:
        errors["plfs"] = plfs_result.error or "data.gov.in PLFS request failed"

    available = bool(values)
    return ProviderResult(
        provider="india_gov",
        dataset="mospi",
        available=available,
        source_url=_MOSPI_CPI_URL,
        data={"values": values, "errors": errors},
        error=None if available else "; ".join(errors.values()),
    )
