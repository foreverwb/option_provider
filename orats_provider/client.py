"""
ORATS API client — synchronous and asynchronous variants.
Covers 6 endpoints: strikes, summaries, cores, monies/implied, ivrank, strikes/options.
Built-in sliding-window rate limiter + optional TTL cache.
"""

from __future__ import annotations

import time
import threading
from typing import Any, Dict, List, Optional

import requests

try:
    import httpx
    _HTTPX = True
except ImportError:
    _HTTPX = False

from .config import OratsConfig, ORATS_BASE_URL
from .cache import TTLCache
from .models import (
    StrikeRecord, SummaryRecord, CoreRecord, MoniesRecord,
    IVRankRecord, OptionRecord,
)


# ── Rate limiter ────────────────────────────────────────────────────────

class _SlidingWindowLimiter:
    """Thread-safe sliding-window rate limiter."""

    def __init__(self, max_requests: int, window_sec: float):
        self._max = max_requests
        self._window = window_sec
        self._timestamps: List[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.time()
                cutoff = now - self._window
                self._timestamps = [t for t in self._timestamps if t > cutoff]
                if len(self._timestamps) < self._max:
                    self._timestamps.append(now)
                    return
                # Calculate wait time
                wait = self._timestamps[0] + self._window - now
            time.sleep(max(0.01, wait))


# ── Synchronous client ──────────────────────────────────────────────────

class OratsClient:
    """Synchronous ORATS API client."""

    def __init__(self, config: Optional[OratsConfig] = None, use_cache: bool = True):
        self.config = config or OratsConfig.from_env()
        self._session = requests.Session()
        self._limiter = _SlidingWindowLimiter(
            self.config.rate_limit, self.config.rate_window_sec,
        )
        self._cache: Optional[TTLCache] = TTLCache(self.config.cache_ttl) if use_cache else None

    def __enter__(self) -> "OratsClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._session.close()

    # ── Raw request ─────────────────────────────────────────────────

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        cache_key = None
        if self._cache and params:
            cache_key = self._cache.make_key(endpoint, str(sorted(params.items())))
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        self._limiter.acquire()
        url = f"{self.config.base_url}/{endpoint}"
        p = dict(params or {})
        p["token"] = self.config.token
        resp = self._session.get(url, params=p, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("data", [])

        if self._cache and cache_key:
            self._cache.set(cache_key, data)
        return data

    # ── Typed endpoints ─────────────────────────────────────────────

    def get_strikes(self, symbol: str, **kwargs: Any) -> List[StrikeRecord]:
        """GET /strikes — full option chain with greeks."""
        params: Dict[str, Any] = {"ticker": symbol.upper()}
        params.update(kwargs)
        return [StrikeRecord.from_orats(r) for r in self._get("strikes", params)]

    def get_summaries(self, symbol: str, **kwargs: Any) -> List[SummaryRecord]:
        """GET /summaries — vol surface summary."""
        params: Dict[str, Any] = {"ticker": symbol.upper()}
        params.update(kwargs)
        return [SummaryRecord.from_orats(r) for r in self._get("summaries", params)]

    def get_cores(self, symbol: str, **kwargs: Any) -> List[CoreRecord]:
        """GET /cores — core vol data."""
        params: Dict[str, Any] = {"ticker": symbol.upper()}
        params.update(kwargs)
        return [CoreRecord.from_orats(r) for r in self._get("cores", params)]

    def get_monies_implied(self, symbol: str, **kwargs: Any) -> List[MoniesRecord]:
        """GET /monies/implied — ATM implied vol by expiry."""
        params: Dict[str, Any] = {"ticker": symbol.upper()}
        params.update(kwargs)
        return [MoniesRecord.from_orats(r) for r in self._get("monies/implied", params)]

    def get_ivrank(self, symbol: str, **kwargs: Any) -> List[IVRankRecord]:
        """GET /ivrank — IV rank and percentile."""
        params: Dict[str, Any] = {"ticker": symbol.upper()}
        params.update(kwargs)
        return [IVRankRecord.from_orats(r) for r in self._get("ivrank", params)]

    def get_options(self, symbol: str, **kwargs: Any) -> List[StrikeRecord]:
        """GET /strikes (alias for get_strikes for options data)."""
        return self.get_strikes(symbol, **kwargs)

    def clear_cache(self) -> None:
        if self._cache:
            self._cache.clear()


# ── Asynchronous client ─────────────────────────────────────────────────

class AsyncOratsClient:
    """Asynchronous ORATS API client (requires httpx)."""

    def __init__(self, config: Optional[OratsConfig] = None, use_cache: bool = True):
        if not _HTTPX:
            raise ImportError("httpx is required for AsyncOratsClient")
        self.config = config or OratsConfig.from_env()
        self._client = httpx.AsyncClient(timeout=30)
        self._cache: Optional[TTLCache] = TTLCache(self.config.cache_ttl) if use_cache else None
        # For async, we use a simple semaphore-based approach
        import asyncio
        self._semaphore = asyncio.Semaphore(self.config.rate_limit)

    async def __aenter__(self) -> "AsyncOratsClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        cache_key = None
        if self._cache and params:
            cache_key = self._cache.make_key(endpoint, str(sorted(params.items())))
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        async with self._semaphore:
            url = f"{self.config.base_url}/{endpoint}"
            p = dict(params or {})
            p["token"] = self.config.token
            resp = await self._client.get(url, params=p)
            resp.raise_for_status()
            data = resp.json().get("data", [])

        if self._cache and cache_key:
            self._cache.set(cache_key, data)
        return data

    async def get_strikes(self, symbol: str, **kwargs: Any) -> List[StrikeRecord]:
        params: Dict[str, Any] = {"ticker": symbol.upper()}
        params.update(kwargs)
        return [StrikeRecord.from_orats(r) for r in await self._get("strikes", params)]

    async def get_summaries(self, symbol: str, **kwargs: Any) -> List[SummaryRecord]:
        params: Dict[str, Any] = {"ticker": symbol.upper()}
        params.update(kwargs)
        return [SummaryRecord.from_orats(r) for r in await self._get("summaries", params)]

    async def get_cores(self, symbol: str, **kwargs: Any) -> List[CoreRecord]:
        params: Dict[str, Any] = {"ticker": symbol.upper()}
        params.update(kwargs)
        return [CoreRecord.from_orats(r) for r in await self._get("cores", params)]

    async def get_monies_implied(self, symbol: str, **kwargs: Any) -> List[MoniesRecord]:
        params: Dict[str, Any] = {"ticker": symbol.upper()}
        params.update(kwargs)
        return [MoniesRecord.from_orats(r) for r in await self._get("monies/implied", params)]

    async def get_ivrank(self, symbol: str, **kwargs: Any) -> List[IVRankRecord]:
        params: Dict[str, Any] = {"ticker": symbol.upper()}
        params.update(kwargs)
        return [IVRankRecord.from_orats(r) for r in await self._get("ivrank", params)]

    async def get_options(self, symbol: str, **kwargs: Any) -> List[StrikeRecord]:
        return await self.get_strikes(symbol, **kwargs)

    def clear_cache(self) -> None:
        if self._cache:
            self._cache.clear()
