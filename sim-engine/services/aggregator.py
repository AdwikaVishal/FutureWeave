import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from data_grounding import detect_industry, detect_role, normalise_location
from services.decision_classifier import classify_decision

from .ambitionbox import fetch_salary
from .common import DataMonitoring, ProviderResult, timed_provider, check_freshness
from .fred import fetch_industry_data
from .sync_data import register_source_health
from .linkedin import fetch_job_trends
from .numbeo import fetch_cost_of_living
from .worldbank import fetch_worldbank
from .job_market import fetch_job_market_intelligence

logger = logging.getLogger("futureweave.data")


class DataGap(BaseModel):
    dataset: str
    message: str
    confidence_delta: int


class EconomicSnapshotPayload(BaseModel):
    role: str
    industry: str
    location: str
    confidence: int
    confidence_explanation: list[str] = Field(default_factory=list)
    gaps: list[DataGap] = Field(default_factory=list)
    providers: dict[str, ProviderResult] = Field(default_factory=dict)
    monitoring: DataMonitoring
    grounding: dict[str, Any] = Field(default_factory=dict)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decision_type: str = "general"
    source_attribution: dict[str, Any] = Field(default_factory=dict)
    data_freshness: dict[str, str] = Field(default_factory=dict)

    def user_messages(self) -> list[str]:
        return [gap.message for gap in self.gaps]


def _score_confidence(results: dict[str, ProviderResult]) -> tuple[int, list[str], list[DataGap]]:
    rules = [
        ("worldbank", "World Bank macro data available", "Real-time World Bank macro data unavailable."),
        ("salary", "Salary data available", "Real-time salary data unavailable."),
        ("cost_of_living", "Cost of living data available", "Real-time cost-of-living data unavailable."),
        ("job_market", "Job market data available", "Real-time job market data unavailable."),
        ("industry", "Industry data available", "Real-time industry data unavailable."),
    ]
    confidence = 100
    explanation = []
    gaps = []
    for key, ok_message, missing_message in rules:
        if results.get(key) and results[key].available:
            explanation.append(f"{ok_message} = +20")
        else:
            previous = confidence
            confidence -= 20
            message = f"{missing_message} Confidence reduced from {previous}% to {confidence}%."
            gaps.append(DataGap(dataset=key, message=message, confidence_delta=-20))
            explanation.append(f"{missing_message} = +0")
    return confidence, explanation, gaps


def _monitor(results: dict[str, ProviderResult]) -> DataMonitoring:
    monitoring = DataMonitoring()
    for key, result in results.items():
        monitoring.api_latency_ms[key] = result.latency_ms
        if result.cache_hit:
            monitoring.cache_hits += 1
        else:
            monitoring.cache_misses += 1
        if not result.available:
            monitoring.api_failures[key] = result.error or "unavailable"
            monitoring.missing_datasets.append(key)
        else:
            if not check_freshness(result, key):
                monitoring.stale_datasets.append(key)
    return monitoring


def _grounding(results: dict[str, ProviderResult]) -> dict[str, Any]:
    grounding: dict[str, Any] = {}
    now = datetime.now(timezone.utc)

    salary = results.get("salary")
    if salary and salary.available:
        grounding["live_salary_range"] = salary.data.get("salary_range_lpa")
        grounding["salary_source"] = salary.provider
        grounding["salary_source_url"] = salary.source_url
        grounding["salary_timestamp"] = salary.fetched_at.isoformat() if salary.fetched_at else now.isoformat()

    worldbank = results.get("worldbank")
    if worldbank and worldbank.available:
        values = worldbank.data.get("values", {})
        years = worldbank.data.get("years", {})
        grounding["live_unemployment"] = values.get("unemployment")
        grounding["live_cpi"] = values.get("inflation")
        grounding["live_gdp_growth"] = values.get("gdp_growth")
        grounding["cpi_year"] = years.get("inflation")
        grounding["cpi_source"] = "world_bank"
        grounding["worldbank_sources"] = worldbank.data.get("sources", {})
        grounding["worldbank_is_historical"] = True
        grounding["worldbank_latest_year"] = worldbank.data.get("latest_year")
        grounding["worldbank_timestamp"] = worldbank.fetched_at.isoformat() if worldbank.fetched_at else now.isoformat()

    col = results.get("cost_of_living")
    if col and col.available:
        grounding["cost_of_living_source"] = col.provider
        grounding["cost_of_living_source_url"] = col.source_url
        grounding["cost_of_living_timestamp"] = col.fetched_at.isoformat() if col.fetched_at else now.isoformat()
        grounding["cost_of_living_data"] = col.data.get("categories", {})
        grounding["cost_of_living_summary"] = col.data.get("summary", {})

    trends = results.get("job_market")
    if trends and trends.available:
        grounding["job_market"] = trends.data
        grounding["job_market_source"] = trends.provider
        grounding["job_market_timestamp"] = trends.fetched_at.isoformat() if trends.fetched_at else now.isoformat()

    industry = results.get("industry")
    if industry and industry.available:
        grounding["industry_data"] = industry.data
        grounding["industry_source"] = industry.provider
        grounding["industry_timestamp"] = industry.fetched_at.isoformat() if industry.fetched_at else now.isoformat()

    return grounding


def _build_source_attribution(results: dict[str, ProviderResult]) -> dict[str, Any]:
    attribution = {}
    now = datetime.now(timezone.utc)
    for key, result in results.items():
        attribution[key] = {
            "provider": result.provider,
            "available": result.available,
            "source_url": result.source_url,
            "fetched_at": result.fetched_at.isoformat() if result.fetched_at else None,
            "latency_ms": result.latency_ms,
            "cache_hit": result.cache_hit,
            "error": result.error,
            "is_historical": result.is_historical,
        }
    return attribution


async def collect_economic_snapshot(decision: str, context: dict, *, country: str = "IN") -> EconomicSnapshotPayload:
    role = detect_role(decision, context)
    industry = detect_industry(decision, context)
    location = normalise_location(context.get("location", "India"))
    decision_profile = classify_decision(decision, context)

    tasks: dict[str, Any] = {}

    if decision_profile.requires_macro_data:
        tasks["worldbank"] = timed_provider("worldbank", "macro", lambda: fetch_worldbank(country))
    else:
        tasks["worldbank"] = timed_provider("worldbank", "macro", lambda: _skip_provider("worldbank", "macro data not required"))

    if decision_profile.requires_salary_data:
        tasks["salary"] = timed_provider("salary", "salary", lambda: fetch_salary(role, location))
    else:
        tasks["salary"] = timed_provider("salary", "salary", lambda: _skip_provider("salary", "salary data not required"))

    if decision_profile.requires_cost_of_living:
        tasks["cost_of_living"] = timed_provider("numbeo", "cost_of_living", lambda: fetch_cost_of_living(location))
    else:
        tasks["cost_of_living"] = timed_provider("numbeo", "cost_of_living", lambda: _skip_provider("numbeo", "cost of living not required"))

    if decision_profile.requires_job_market:
        tasks["job_market"] = timed_provider(
            "job_market", "job_market",
            lambda: asyncio.ensure_future(_fetch_job_market(role, location)),
        )
    else:
        tasks["job_market"] = timed_provider(
            "job_market", "job_market",
            lambda: asyncio.ensure_future(_skip_job_market()),
        )

    if decision_profile.requires_business_data:
        tasks["industry"] = timed_provider("fred", "industry", lambda: fetch_industry_data(industry))
    else:
        tasks["industry"] = timed_provider("fred", "industry", lambda: _skip_provider("fred", "industry data not required"))

    values = await asyncio.gather(*tasks.values(), return_exceptions=False)
    results = dict(zip(tasks.keys(), values))

    for key, result in results.items():
        if result.available:
            register_source_health(key, True, result.source_url or "")
        else:
            register_source_health(key, False, error=result.error or "unavailable")

    confidence, explanation, gaps = _score_confidence(results)
    monitoring = _monitor(results)
    grounding = _grounding(results)
    source_attribution = _build_source_attribution(results)

    data_freshness = {}
    for key, result in results.items():
        if result.available:
            is_stale = not check_freshness(result, key)
            data_freshness[key] = "stale" if is_stale else "fresh"
        else:
            data_freshness[key] = "unavailable"

    logger.info(
        "[LIVE_DATA] Economic snapshot: role=%s location=%s confidence=%s decision_type=%s missing=%s stale=%s",
        role, location, confidence, decision_profile.category.value,
        monitoring.missing_datasets, monitoring.stale_datasets,
    )

    return EconomicSnapshotPayload(
        role=role,
        industry=industry,
        location=location,
        confidence=confidence,
        confidence_explanation=explanation,
        gaps=gaps,
        providers=results,
        monitoring=monitoring,
        grounding=grounding,
        source_attribution=source_attribution,
        data_freshness=data_freshness,
        decision_type=decision_profile.category.value,
    )


async def _fetch_job_market(role: str, location: str) -> ProviderResult:
    result = await fetch_job_market_intelligence(role, location)
    if result.get("success"):
        return ProviderResult(
            provider=result["source"],
            dataset="job_market",
            available=True,
            data=result["data"],
        )
    return ProviderResult(
        provider="job_market",
        dataset="job_market",
        available=False,
        error=result.get("error", "Job market intelligence unavailable"),
    )


async def _skip_job_market() -> ProviderResult:
    return ProviderResult(
        provider="job_market",
        dataset="job_market",
        available=False,
        error="Job market data not required for this decision type",
    )


async def _skip_provider(provider: str, reason: str) -> ProviderResult:
    return ProviderResult(
        provider=provider,
        dataset=provider,
        available=False,
        error=f"{provider} skipped: {reason}",
    )
