import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger("futureweave.data")


class ProviderResult(BaseModel):
    provider: str
    dataset: str
    available: bool
    data: Any = Field(default_factory=dict)
    source_url: Optional[str] = None
    latency_ms: float = 0
    cache_hit: bool = False
    error: Optional[str] = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_historical: bool = False
    data_year: Optional[str] = None


class DataMonitoring(BaseModel):
    api_latency_ms: dict[str, float] = Field(default_factory=dict)
    api_failures: dict[str, str] = Field(default_factory=dict)
    missing_datasets: list[str] = Field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0
    stale_datasets: list[str] = Field(default_factory=list)


class AsyncTTLCache:
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = timedelta(seconds=ttl_seconds)
        self._memory: dict[str, tuple[datetime, Any]] = {}
        self._redis = None
        self._redis_checked = False

    async def _get_redis(self):
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            return None
        try:
            import redis.asyncio as redis
            self._redis = redis.from_url(redis_url, decode_responses=True)
            await self._redis.ping()
            logger.info("Redis cache connected")
        except Exception as exc:
            logger.warning("Redis unavailable, using in-memory cache: %s", exc)
            self._redis = None
        return self._redis

    async def get(self, key: str):
        redis = await self._get_redis()
        if redis:
            raw = await redis.get(key)
            if raw is not None:
                return json.loads(raw)
        entry = self._memory.get(key)
        if not entry:
            return None
        stored_at, value = entry
        if datetime.now(timezone.utc) - stored_at > self.ttl:
            self._memory.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any):
        redis = await self._get_redis()
        if redis:
            await redis.setex(key, int(self.ttl.total_seconds()), json.dumps(value, default=str))
            return value
        self._memory[key] = (datetime.now(timezone.utc), value)
        return value


cache = AsyncTTLCache(ttl_seconds=int(os.environ.get("DATA_CACHE_TTL_SECONDS", "21600")))


async def fetch_json(
    provider: str,
    dataset: str,
    url: str,
    *,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    timeout: float = 10,
    retries: int = 2,
) -> ProviderResult:
    cache_key = f"data:{provider}:{dataset}:{url}:{json.dumps(params or {}, sort_keys=True)}"
    cached = await cache.get(cache_key)
    if cached is not None:
        return ProviderResult(
            provider=provider,
            dataset=dataset,
            available=True,
            data=cached,
            source_url=url,
            cache_hit=True,
        )

    start = time.perf_counter()
    last_error = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                payload = response.json()
                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                await cache.set(cache_key, payload)

                logger.info(
                    "[LIVE_DATA] Source=%s Dataset=%s URL=%s Status=%d ResponseTime=%.0fms",
                    provider, dataset, url, response.status_code, latency_ms,
                )

                return ProviderResult(
                    provider=provider,
                    dataset=dataset,
                    available=True,
                    data=payload,
                    source_url=str(response.url),
                    latency_ms=latency_ms,
                )
        except Exception as exc:
            last_error = str(exc)
            if attempt < retries:
                await asyncio.sleep(0.3 * (2**attempt))

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.warning(
        "[LIVE_DATA] Source=%s Dataset=%s Status=ERROR ResponseTime=%.0fms Error=%s",
        provider, dataset, latency_ms, last_error,
    )
    return ProviderResult(
        provider=provider,
        dataset=dataset,
        available=False,
        source_url=url,
        latency_ms=latency_ms,
        error=last_error or "request failed",
    )


async def timed_provider(
    provider: str,
    dataset: str,
    func: Callable[[], Awaitable[ProviderResult]],
) -> ProviderResult:
    start = time.perf_counter()
    try:
        result = await func()
        if result.latency_ms == 0 and not result.cache_hit:
            result.latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return result
    except Exception as exc:
        return ProviderResult(
            provider=provider,
            dataset=dataset,
            available=False,
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
            error=str(exc),
        )


STALE_THRESHOLDS = {
    "job_market": timedelta(days=7),
    "salary": timedelta(days=90),
    "cost_of_living": timedelta(days=180),
}


def check_freshness(result: ProviderResult, dataset_type: str) -> bool:
    threshold = STALE_THRESHOLDS.get(dataset_type)
    if threshold is None:
        return True
    age = datetime.now(timezone.utc) - result.fetched_at
    if age > threshold:
        logger.warning(
            "[STALE_DATA] %s dataset=%s age=%.1fd threshold=%dd",
            result.provider, dataset_type, age.total_seconds() / 86400, threshold.days,
        )
        return False
    return True


def log_live_data(source: str, url: str, status: int | str, response_time_ms: float, parsed: Any = None, error: str = ""):
    if error:
        logger.info(
            "[LIVE_DATA] Source=%s Status=%s ResponseTime=%.0fms Error=%s",
            source, status, response_time_ms, error,
        )
    else:
        logger.info(
            "[LIVE_DATA] Source=%s Status=%d ResponseTime=%.0fms Result=%s",
            source, status, response_time_ms, str(parsed)[:200] if parsed else "None",
        )
