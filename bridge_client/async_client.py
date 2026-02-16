from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from .models import BridgeSnapshot


class AsyncBridgeClient:
    """
    Async HTTP client for volatility_analysis bridge endpoints.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8668",
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(base_url=self.base_url, timeout=timeout)

    @staticmethod
    def _ensure_success(payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError(f"Unexpected bridge payload type: {type(payload).__name__}")
        if payload.get("success") is False:
            raise ValueError(str(payload.get("error") or "Bridge API returned success=False"))
        return payload

    async def get_bridge_snapshot(
        self,
        symbol: str,
        date: Optional[str] = None,
        source: Optional[str] = None,
    ) -> BridgeSnapshot:
        params: Dict[str, str] = {}
        if date:
            params["date"] = date
        if source:
            params["source"] = source

        response = await self.client.get(f"/api/bridge/params/{symbol.upper()}", params=params)
        response.raise_for_status()
        payload = self._ensure_success(response.json())
        bridge_data = payload.get("bridge") or payload.get("data")
        if not isinstance(bridge_data, dict):
            raise ValueError("Bridge snapshot payload missing 'bridge' object")
        snapshot = BridgeSnapshot.from_dict(bridge_data)
        if not snapshot.symbol:
            snapshot.symbol = symbol.upper()
        return snapshot

    async def get_bridge_batch(
        self,
        symbols: Optional[List[str]] = None,
        date: Optional[str] = None,
        source: str = "swing",
        min_direction_score: float = 1.0,
        min_vol_score: float = 0.8,
        limit: int = 50,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "source": source,
            "limit": int(limit),
            "min_direction_score": float(min_direction_score),
            "min_vol_score": float(min_vol_score),
        }
        if date:
            body["date"] = date
        if symbols:
            body["symbols"] = [s.upper() for s in symbols]

        response = await self.client.post("/api/bridge/batch", json=body)
        response.raise_for_status()
        return self._ensure_success(response.json())

    async def get_records(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"date": date} if date else None
        response = await self.client.get("/api/records", params=params)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            records = payload.get("results") or payload.get("data")
            if isinstance(records, list):
                return records
        raise ValueError("Unexpected /api/records response shape")

    async def get_config(self) -> Dict[str, Any]:
        response = await self.client.get("/api/config")
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("config"), dict):
            return payload["config"]
        if isinstance(payload, dict):
            return payload
        raise ValueError("Unexpected /api/config response shape")

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def __aenter__(self) -> "AsyncBridgeClient":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()
