"""
HTTP client for the volatility_analysis Bridge API.
Provides both synchronous (BridgeClient) and asynchronous (AsyncBridgeClient) interfaces.
Targets endpoints on http://<host>:8668.
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

    # --- Context manager ---
    def __enter__(self) -> "BridgeClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._session.close()

    # --- Endpoints ---
    def get_snapshot(self, symbol: str) -> BridgeSnapshot:
        """GET /api/bridge/params/<symbol>"""
        url = f"{self.base_url}/api/bridge/params/{symbol.upper()}"
        resp = self._session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return BridgeSnapshot.from_dict(resp.json())

    def get_batch(
        self,
        symbols: Optional[List[str]] = None,
        source: Optional[str] = None,
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
        if filtering:
            payload["filtering"] = filtering
        if sorting:
            payload["sorting"] = sorting
        resp = self._session.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("results", data.get("snapshots", []))
        return [BridgeSnapshot.from_dict(item) for item in items]

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

    async def get_snapshot(self, symbol: str) -> BridgeSnapshot:
        resp = await self._client.get(f"/api/bridge/params/{symbol.upper()}")
        resp.raise_for_status()
        return BridgeSnapshot.from_dict(resp.json())

    async def get_batch(
        self,
        symbols: Optional[List[str]] = None,
        source: Optional[str] = None,
        filtering: Optional[Dict[str, Any]] = None,
        sorting: Optional[Dict[str, Any]] = None,
    ) -> List[BridgeSnapshot]:
        payload: Dict[str, Any] = {}
        if symbols:
            payload["symbols"] = [s.upper() for s in symbols]
        if source:
            payload["source"] = source
        if filtering:
            payload["filtering"] = filtering
        if sorting:
            payload["sorting"] = sorting
        resp = await self._client.post("/api/bridge/batch", json=payload)
        resp.raise_for_status()
        data = resp.json()
        items = data if isinstance(data, list) else data.get("results", data.get("snapshots", []))
        return [BridgeSnapshot.from_dict(item) for item in items]

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
