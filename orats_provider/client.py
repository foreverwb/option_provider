from __future__ import annotations

import asyncio
import csv
import io
import time
from typing import Any, Dict, List, Optional

import httpx

from .cache import TTLCache
from .config import CACHE_TTL_SECONDS, ORATS_BASE_URL, ORATS_TOKEN


class OratsClientError(RuntimeError):
    """ORATS client request/payload error."""


class OratsClient:
    """
    ORATS Delayed Data API sync client.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = ORATS_BASE_URL,
        rate_limit: int = 60,
        timeout: float = 30.0,
        cache: Optional[TTLCache] = None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.token = token if token is not None else ORATS_TOKEN
        self.base_url = base_url.rstrip("/")
        self.rate_limit = int(rate_limit)
        self._request_times: List[float] = []
        self.cache = cache or TTLCache(CACHE_TTL_SECONDS)
        self._owns_client = client is None
        self.client = client or httpx.Client(base_url=self.base_url, timeout=timeout)

    def _throttle(self) -> None:
        now = time.monotonic()
        self._request_times = [t for t in self._request_times if now - t < 60.0]
        if len(self._request_times) >= self.rate_limit and self._request_times:
            sleep_time = 60.0 - (now - self._request_times[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        self._request_times.append(time.monotonic())

    @staticmethod
    def _cache_key(endpoint: str, params: Dict[str, Any]) -> str:
        items = sorted((str(k), str(v)) for k, v in params.items())
        joined = "&".join(f"{k}={v}" for k, v in items)
        return f"{endpoint}?{joined}"

    @staticmethod
    def _parse_response(resp: httpx.Response) -> Dict[str, Any]:
        content_type = resp.headers.get("content-type", "").lower()
        if "application/json" in content_type or not content_type:
            payload = resp.json()
            if isinstance(payload, dict):
                return payload
            if isinstance(payload, list):
                return {"data": payload}
            raise OratsClientError("Unexpected ORATS JSON response type")

        if "text/csv" in content_type or "application/csv" in content_type:
            decoded = resp.text
            reader = csv.DictReader(io.StringIO(decoded))
            return {"data": list(reader)}

        raise OratsClientError(f"Unsupported ORATS content type: {content_type}")

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._throttle()

        params = dict(params or {})
        if self.token:
            params["token"] = self.token

        key = self._cache_key(endpoint, params)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        resp = self.client.get(endpoint, params=params)
        resp.raise_for_status()
        payload = self._parse_response(resp)
        self.cache.set(key, payload)
        return payload

    def get_strikes(
        self,
        ticker: str,
        dte: Optional[str] = None,
        delta: Optional[str] = None,
        fields: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"ticker": ticker}
        if dte:
            params["dte"] = dte
        if delta:
            params["delta"] = delta
        if fields:
            params["fields"] = fields
        data = self._get("/datav2/strikes", params)
        return data.get("data", [])

    def get_strikes_options(self, tickers: str) -> List[Dict[str, Any]]:
        data = self._get("/datav2/strikes/options", {"tickers": tickers})
        return data.get("data", [])

    def get_summaries(self, ticker: str, fields: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"ticker": ticker}
        if fields:
            params["fields"] = fields
        data = self._get("/datav2/summaries", params)
        return data.get("data", [])

    def get_cores(self, ticker: str, fields: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"ticker": ticker}
        if fields:
            params["fields"] = fields
        data = self._get("/datav2/cores", params)
        return data.get("data", [])

    def get_monies_implied(self, ticker: str, fields: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"ticker": ticker}
        if fields:
            params["fields"] = fields
        data = self._get("/datav2/monies/implied", params)
        return data.get("data", [])

    def get_monies_forecast(self, ticker: str, fields: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"ticker": ticker}
        if fields:
            params["fields"] = fields
        data = self._get("/datav2/monies/forecast", params)
        return data.get("data", [])

    def get_iv_rank(self, ticker: str) -> List[Dict[str, Any]]:
        data = self._get("/datav2/ivrank", {"ticker": ticker})
        return data.get("data", [])

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "OratsClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


class AsyncOratsClient:
    """
    ORATS Delayed Data API async client.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = ORATS_BASE_URL,
        rate_limit: int = 60,
        timeout: float = 30.0,
        cache: Optional[TTLCache] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.token = token if token is not None else ORATS_TOKEN
        self.base_url = base_url.rstrip("/")
        self.rate_limit = int(rate_limit)
        self._request_times: List[float] = []
        self.cache = cache or TTLCache(CACHE_TTL_SECONDS)
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    async def _throttle(self) -> None:
        now = time.monotonic()
        self._request_times = [t for t in self._request_times if now - t < 60.0]
        if len(self._request_times) >= self.rate_limit and self._request_times:
            sleep_time = 60.0 - (now - self._request_times[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        self._request_times.append(time.monotonic())

    @staticmethod
    def _cache_key(endpoint: str, params: Dict[str, Any]) -> str:
        items = sorted((str(k), str(v)) for k, v in params.items())
        joined = "&".join(f"{k}={v}" for k, v in items)
        return f"{endpoint}?{joined}"

    @staticmethod
    def _parse_response(resp: httpx.Response) -> Dict[str, Any]:
        content_type = resp.headers.get("content-type", "").lower()
        if "application/json" in content_type or not content_type:
            payload = resp.json()
            if isinstance(payload, dict):
                return payload
            if isinstance(payload, list):
                return {"data": payload}
            raise OratsClientError("Unexpected ORATS JSON response type")

        if "text/csv" in content_type or "application/csv" in content_type:
            decoded = resp.text
            reader = csv.DictReader(io.StringIO(decoded))
            return {"data": list(reader)}

        raise OratsClientError(f"Unsupported ORATS content type: {content_type}")

    async def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        await self._throttle()

        params = dict(params or {})
        if self.token:
            params["token"] = self.token

        key = self._cache_key(endpoint, params)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        resp = await self.client.get(endpoint, params=params)
        resp.raise_for_status()
        payload = self._parse_response(resp)
        self.cache.set(key, payload)
        return payload

    async def get_strikes(
        self,
        ticker: str,
        dte: Optional[str] = None,
        delta: Optional[str] = None,
        fields: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"ticker": ticker}
        if dte:
            params["dte"] = dte
        if delta:
            params["delta"] = delta
        if fields:
            params["fields"] = fields
        data = await self._get("/datav2/strikes", params)
        return data.get("data", [])

    async def get_summaries(self, ticker: str, fields: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"ticker": ticker}
        if fields:
            params["fields"] = fields
        data = await self._get("/datav2/summaries", params)
        return data.get("data", [])

    async def get_cores(self, ticker: str, fields: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"ticker": ticker}
        if fields:
            params["fields"] = fields
        data = await self._get("/datav2/cores", params)
        return data.get("data", [])

    async def get_monies_implied(self, ticker: str, fields: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"ticker": ticker}
        if fields:
            params["fields"] = fields
        data = await self._get("/datav2/monies/implied", params)
        return data.get("data", [])

    async def get_monies_forecast(self, ticker: str, fields: Optional[str] = None) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"ticker": ticker}
        if fields:
            params["fields"] = fields
        data = await self._get("/datav2/monies/forecast", params)
        return data.get("data", [])

    async def get_iv_rank(self, ticker: str) -> List[Dict[str, Any]]:
        data = await self._get("/datav2/ivrank", {"ticker": ticker})
        return data.get("data", [])

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def __aenter__(self) -> "AsyncOratsClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()
