import logging
import os
from datetime import datetime, timezone

from .common import ProviderResult, cache
from .job_market import fetch_adzuna_jobs, fetch_jsearch_jobs

logger = logging.getLogger("futureweave.data")

ROLE_QUERY_MAP = {
    "software engineer": "software engineer",
    "data scientist": "data scientist",
    "product manager": "product manager",
    "mechanical engineer": "mechanical engineer",
    "designer": "designer",
    "software engineer": "software engineer",
    "doctor": "doctor physician",
    "nurse": "nurse",
    "teacher": "teacher",
    "professor": "professor",
    "accountant": "accountant",
    "lawyer": "lawyer",
    "civil engineer": "civil engineer",
    "default": "software engineer",
}


async def fetch_salary(role: str, location: str) -> ProviderResult:
    query_role = ROLE_QUERY_MAP.get(role, ROLE_QUERY_MAP["default"])
    cache_key = f"data:salary:live:{query_role}:{location}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return ProviderResult(
            provider="salary_aggregator",
            dataset="salary",
            available=True,
            data=cached,
            source_url="aggregated",
            cache_hit=True,
        )

    adzuna_error = None
    job_result = await fetch_adzuna_jobs(query_role, location)
    if job_result.available:
        data = job_result.data
        salary_info = data.get("salary_summary")
        if salary_info and salary_info.get("avg_min"):
            lpa_min = salary_info["avg_min"] / 100000 if salary_info.get("currency") == "INR" else salary_info["avg_min"] * 83 / 100000
            lpa_max = salary_info["avg_max"] / 100000 if salary_info.get("currency") == "INR" else salary_info["avg_max"] * 83 / 100000
            parsed = {
                "role": role,
                "location": location,
                "salary_range_lpa": [round(lpa_min, 1), round(lpa_max, 1)],
                "source": "adzuna",
            }
            await cache.set(cache_key, parsed)
            logger.info(
                "[LIVE_DATA] Source=AdzunaSalary Status=200 Role=%s Location=%s Range=%s LPA",
                role, location, parsed["salary_range_lpa"],
            )
            return ProviderResult(
                provider="adzuna",
                dataset="salary",
                available=True,
                data=parsed,
                source_url="https://api.adzuna.com/v1/api/jobs",
            )
    else:
        adzuna_error = job_result.error or "Adzuna API unavailable (no API key or timeout)"

    jsearch_error = None
    jsearch_result = await fetch_jsearch_jobs(query_role, location)
    if jsearch_result.available:
        data = jsearch_result.data
        salary_info = data.get("salary_summary")
        if salary_info and salary_info.get("avg_min"):
            lpa_min = salary_info["avg_min"] / 100000
            lpa_max = salary_info["avg_max"] / 100000
            parsed = {
                "role": role,
                "location": location,
                "salary_range_lpa": [round(lpa_min, 1), round(lpa_max, 1)],
                "source": "jsearch",
            }
            await cache.set(cache_key, parsed)
            logger.info(
                "[LIVE_DATA] Source=JSearchSalary Status=200 Role=%s Location=%s Range=%s LPA",
                role, location, parsed["salary_range_lpa"],
            )
            return ProviderResult(
                provider="jsearch",
                dataset="salary",
                available=True,
                data=parsed,
                source_url="https://jsearch.p.rapidapi.com",
            )
    else:
        jsearch_error = jsearch_result.error or "JSearch API unavailable (no RAPIDAPI_KEY or timeout)"

    error_detail = f"Adzuna: {adzuna_error} | JSearch: {jsearch_error}"
    logger.warning(
        "[LIVE_DATA] Source=SalaryAggregator Status=UNAVAILABLE Role=%s Location=%s Detail=%s",
        role, location, error_detail,
    )
    return ProviderResult(
        provider="salary_aggregator",
        dataset="salary",
        available=False,
        error=error_detail,
    )
