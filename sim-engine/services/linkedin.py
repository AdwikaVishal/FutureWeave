import os

from .common import ProviderResult, fetch_json


async def fetch_job_trends(role: str, location: str) -> ProviderResult:
    api_url = os.environ.get("LINKEDIN_TRENDS_API_URL")
    api_key = os.environ.get("LINKEDIN_TRENDS_API_KEY")
    if not api_url or not api_key:
        return ProviderResult(
            provider="linkedin",
            dataset="job_trends",
            available=False,
            error="LinkedIn/job trends API is not configured",
        )

    result = await fetch_json(
        "linkedin",
        "job_trends",
        api_url,
        params={"role": role, "location": location},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return result

