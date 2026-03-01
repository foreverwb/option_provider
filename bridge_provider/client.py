"""
HTTP client for the Bridge API.
Provides both synchronous (BridgeClient) and asynchronous (AsyncBridgeClient) interfaces.
Targets endpoints on the configured bridge service URL.

v2.0: Enhanced get_snapshot/get_batch with date, source, and filtering params.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import requests

try:
    import httpx

    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

from .models import BridgeSnapshot


class BridgeClient:
    """Synchronous HTTP client for the Bridge API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8668",
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        if headers:
            self._session.headers.update(headers)

    def __enter__(self) -> "BridgeClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._session.close()

    # --- Endpoints ---

    def get_snapshot(
        self,
        symbol: str,
        date: Optional[str] = None,
        source: Optional[str] = None,
    ) -> BridgeSnapshot:
        """GET /api/bridge/params/<symbol>"""
        url = f"{self.base_url}/api/bridge/params/{symbol.upper()}"
        params: Dict[str, Any] = {}
        if date:
            params["date"] = date
        if source:
            params["source"] = source
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        # Handle VA-style wrapped response
        if isinstance(data, dict):
            if data.get("success") is True and isinstance(data.get("bridge"), dict):
                return BridgeSnapshot.from_dict(data["bridge"])
            if data.get("bridge") is not None:
                return BridgeSnapshot.from_dict(data["bridge"])
        return BridgeSnapshot.from_dict(data)

    def get_batch(
        self,
        symbols: Optional[List[str]] = None,
        source: Optional[str] = None,
        date: Optional[str] = None,
        min_direction_score: Optional[float] = None,
        min_vol_score: Optional[float] = None,
        limit: Optional[int] = None,
        filtering: Optional[Dict[str, Any]] = None,
        sorting: Optional[Dict[str, Any]] = None,
    ) -> List[BridgeSnapshot]:
        """POST /api/bridge/batch"""
        url = f"{self.base_url}/api/bridge/batch"
        payload: Dict[str, Any] = {}
        if symbols:
            payload["symbols"] = [s.upper() for s in symbols]
        if source:
            payload["source"] = source
        if date:
            payload["date"] = date
        if min_direction_score is not None:
            payload["min_direction_score"] = min_direction_score
        if min_vol_score is not None:
            payload["min_vol_score"] = min_vol_score
        if limit is not None:
            payload["limit"] = limit
        if filtering:
            payload["filtering"] = filtering
        if sorting:
            payload["sorting"] = sorting

        resp = self._session.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        # Handle various response formats
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("results", data.get("snapshots", []))
        else:
            items = []

        return [BridgeSnapshot.from_dict(item) for item in items if isinstance(item, dict)]

    def get_records(self, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """GET /api/records"""
        url = f"{self.base_url}/api/records"
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_config(self) -> Dict[str, Any]:
        """GET /api/config"""
        url = f"{self.base_url}/api/config"
        resp = self._session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def update_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """POST /api/config"""
        url = f"{self.base_url}/api/config"
        resp = self._session.post(url, json=config, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def analyze(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST /api/analyze"""
        url = f"{self.base_url}/api/analyze"
        resp = self._session.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()


class AsyncBridgeClient:
    """Asynchronous HTTP client for the Bridge API (requires httpx)."""

    def __init__(
        self,
        base_url: str = "http://localhost:8668",
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        if not _HTTPX_AVAILABLE:
            raise ImportError("httpx is required for AsyncBridgeClient: pip install httpx")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers=headers or {},
        )

    async def __aenter__(self) -> "AsyncBridgeClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def get_snapshot(
        self,
        symbol: str,
        date: Optional[str] = None,
        source: Optional[str] = None,
    ) -> BridgeSnapshot:
        params: Dict[str, Any] = {}
        if date:
            params["date"] = date
        if source:
            params["source"] = source
        resp = await self._client.get(
            f"/api/bridge/params/{symbol.upper()}", params=params
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            if data.get("success") is True and isinstance(data.get("bridge"), dict):
                return BridgeSnapshot.from_dict(data["bridge"])
            if data.get("bridge") is not None:
                return BridgeSnapshot.from_dict(data["bridge"])
        return BridgeSnapshot.from_dict(data)

    async def get_batch(
        self,
        symbols: Optional[List[str]] = None,
        source: Optional[str] = None,
        date: Optional[str] = None,
        min_direction_score: Optional[float] = None,
        min_vol_score: Optional[float] = None,
        limit: Optional[int] = None,
        filtering: Optional[Dict[str, Any]] = None,
        sorting: Optional[Dict[str, Any]] = None,
    ) -> List[BridgeSnapshot]:
        payload: Dict[str, Any] = {}
        if symbols:
            payload["symbols"] = [s.upper() for s in symbols]
        if source:
            payload["source"] = source
        if date:
            payload["date"] = date
        if min_direction_score is not None:
            payload["min_direction_score"] = min_direction_score
        if min_vol_score is not None:
            payload["min_vol_score"] = min_vol_score
        if limit is not None:
            payload["limit"] = limit
        if filtering:
            payload["filtering"] = filtering
        if sorting:
            payload["sorting"] = sorting

        resp = await self._client.post("/api/bridge/batch", json=payload)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("results", data.get("snapshots", []))
        else:
            items = []
        return [BridgeSnapshot.from_dict(item) for item in items if isinstance(item, dict)]

    async def get_records(self, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        resp = await self._client.get("/api/records", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_config(self) -> Dict[str, Any]:
        resp = await self._client.get("/api/config")
        resp.raise_for_status()
        return resp.json()

    async def update_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        resp = await self._client.post("/api/config", json=config)
        resp.raise_for_status()
        return resp.json()

    async def analyze(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = await self._client.post("/api/analyze", json=payload)
        resp.raise_for_status()
        return resp.json()
