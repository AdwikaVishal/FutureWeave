import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from .common import ProviderResult, fetch_json, cache

logger = logging.getLogger("futureweave.data")

ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs"


async def fetch_adzuna_jobs(
    role: str,
    location: str = "India",
    country: str = "in",
) -> ProviderResult:
    app_id = os.environ.get("ADZUNA_APP_ID")
    api_key = os.environ.get("ADZUNA_API_KEY")

    if not app_id or not api_key:
        return ProviderResult(
            provider="adzuna",
            dataset="job_market",
            available=False,
            error="ADZUNA_APP_ID or ADZUNA_API_KEY not configured",
        )

    cache_key = f"data:adzuna:jobs:{role}:{country}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return ProviderResult(
            provider="adzuna",
            dataset="job_market",
            available=True,
            data=cached,
            cache_hit=True,
        )

    url = f"{ADZUNA_BASE}/{country}/search/1"
    params = {
        "app_id": app_id,
        "app_key": api_key,
        "what": role,
        "where": location,
        "content-type": "application/json",
        "results_per_page": 50,
    }

    result = await fetch_json("adzuna", "job_market", url, params=params, timeout=15)

    if not result.available:
        return result

    raw = result.data
    listings = raw.get("results", [])
    total_jobs = raw.get("count", 0)

    salaries = []
    skills = {}
    for listing in listings:
        min_sal = listing.get("salary_min")
        max_sal = listing.get("salary_max")
        if min_sal and max_sal:
            salaries.append((min_sal, max_sal))
        description = listing.get("description", "").lower()
        for skill in _SKILL_KEYWORDS:
            if skill in description:
                skills[skill] = skills.get(skill, 0) + 1

    parsed = {
        "total_jobs": total_jobs,
        "listings_returned": len(listings),
        "salary_summary": _salary_summary(salaries) if salaries else None,
        "skills_demand": sorted(skills.items(), key=lambda x: x[1], reverse=True)[:15] if skills else [],
        "role": role,
        "location": location,
        "source": "adzuna",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "[LIVE_DATA] Source=Adzuna Status=200 JobsFound=%d ResponseTime=%.0fms",
        total_jobs, result.latency_ms,
    )

    await cache.set(cache_key, parsed)
    result.data = parsed
    return result


async def fetch_jsearch_jobs(
    role: str,
    location: str = "India",
) -> ProviderResult:
    api_key = os.environ.get("RAPIDAPI_KEY")
    if not api_key:
        return ProviderResult(
            provider="jsearch",
            dataset="job_market",
            available=False,
            error="RAPIDAPI_KEY not configured",
        )

    cache_key = f"data:jsearch:jobs:{role}:{location}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return ProviderResult(
            provider="jsearch",
            dataset="job_market",
            available=True,
            data=cached,
            cache_hit=True,
        )

    url = "https://jsearch.p.rapidapi.com/search"
    params = {
        "query": f"{role} in {location}",
        "page": "1",
        "num_pages": "1",
    }
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }

    result = await fetch_json("jsearch", "job_market", url, params=params, headers=headers, timeout=15)

    if not result.available:
        return result

    raw = result.data
    jobs = raw.get("data", [])
    total_jobs = len(jobs)

    salaries = []
    skills = {}
    for job in jobs:
        min_sal = job.get("job_min_salary")
        max_sal = job.get("job_max_salary")
        if min_sal and max_sal:
            salaries.append((min_sal, max_sal))
        desc = (job.get("job_description") or "").lower()
        for skill in _SKILL_KEYWORDS:
            if skill in desc:
                skills[skill] = skills.get(skill, 0) + 1
        title = (job.get("job_title") or "").lower()
        for skill in _SKILL_KEYWORDS:
            if skill in title:
                skills[skill] = skills.get(skill, 0) + 1

    parsed = {
        "total_jobs": total_jobs,
        "listings_returned": len(jobs),
        "salary_summary": _salary_summary(salaries) if salaries else None,
        "skills_demand": sorted(skills.items(), key=lambda x: x[1], reverse=True)[:15] if skills else [],
        "role": role,
        "location": location,
        "source": "jsearch",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "[LIVE_DATA] Source=JSearch Status=200 JobsFound=%d ResponseTime=%.0fms",
        total_jobs, result.latency_ms,
    )

    await cache.set(cache_key, parsed)
    result.data = parsed
    return result


_SKILL_KEYWORDS = [
    "python", "javascript", "java", "typescript", "react", "angular", "vue",
    "node", "django", "flask", "spring", "sql", "nosql", "mongodb", "postgresql",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd",
    "machine learning", "deep learning", "nlp", "computer vision", "tensorflow",
    "pytorch", "data analysis", "data science", "tableau", "power bi",
    "product management", "agile", "scrum", "leadership", "communication",
    "cybersecurity", "network security", "cloud security", "devsecops",
    "flutter", "swift", "kotlin", "go", "rust", "c++", "c#", ".net",
    "blockchain", "solidity", "web3",
]


def _salary_summary(salaries: list[tuple[float, float]]) -> dict[str, Any]:
    if not salaries:
        return {}
    mins = [s[0] for s in salaries if s[0]]
    maxs = [s[1] for s in salaries if s[1]]
    return {
        "min_annual": round(min(mins), 2) if mins else None,
        "max_annual": round(max(maxs), 2) if maxs else None,
        "avg_min": round(sum(mins) / len(mins), 2) if mins else None,
        "avg_max": round(sum(maxs) / len(maxs), 2) if maxs else None,
        "median_min": sorted(mins)[len(mins) // 2] if mins else None,
        "median_max": sorted(maxs)[len(maxs) // 2] if maxs else None,
        "currency": "INR" if any(s > 100000 for s in mins) else "USD",
        "sample_size": len(salaries),
    }


async def fetch_job_market_intelligence(role: str, location: str = "India") -> dict:
    result = await fetch_adzuna_jobs(role, location)
    if result.available:
        return {
            "success": True,
            "source": "adzuna",
            "data": result.data,
            "fetched_at": result.fetched_at.isoformat(),
            "latency_ms": result.latency_ms,
        }

    result = await fetch_jsearch_jobs(role, location)
    if result.available:
        return {
            "success": True,
            "source": "jsearch",
            "data": result.data,
            "fetched_at": result.fetched_at.isoformat(),
            "latency_ms": result.latency_ms,
        }

    return {
        "success": False,
        "source": "job_market",
        "error": "No job market API configured or available",
        "confidence": "low",
    }
