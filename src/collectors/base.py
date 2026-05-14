from __future__ import annotations
import asyncio
import logging
import random
from abc import ABC
from typing import Optional, Dict

import httpx

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: float = 1.0):
        self.max_requests = max_requests
        self.window = window_seconds
        self._timestamps: list[float] = []

    async def acquire(self):
        now = asyncio.get_event_loop().time()
        self._timestamps = [t for t in self._timestamps if now - t < self.window]
        if len(self._timestamps) >= self.max_requests:
            wait = self._timestamps[0] + self.window - now
            if wait > 0:
                logger.debug(f"[RateLimit] Aguardando {wait:.2f}s")
                await asyncio.sleep(wait)
        self._timestamps.append(asyncio.get_event_loop().time())


_pool_client: Optional[httpx.AsyncClient] = None
_rate_limiter = RateLimiter(max_requests=10)


def get_http_client() -> httpx.AsyncClient:
    global _pool_client
    if _pool_client is None:
        _pool_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            follow_redirects=True,
        )
    return _pool_client


async def retry_with_backoff(
    coro_factory,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retry_on: tuple = (429, 500, 502, 503, 504),
):
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in retry_on and attempt < max_retries:
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                logger.warning(f"[Retry] HTTP {e.response.status_code}, tentativa {attempt+1}/{max_retries}, aguardando {delay:.1f}s")
                await asyncio.sleep(delay)
                continue
            raise
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                logger.warning(f"[Retry] {type(e).__name__}, tentativa {attempt+1}/{max_retries}, aguardando {delay:.1f}s")
                await asyncio.sleep(delay)
                continue
            raise
    return None


class BaseCollector(ABC):
    def __init__(self, headers: Optional[Dict] = None):
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def _get_json(self, url: str, params: dict | None = None):
        await _rate_limiter.acquire()

        async def _fetch():
            client = get_http_client()
            resp = await client.get(url, params=params, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

        return await retry_with_backoff(_fetch)
