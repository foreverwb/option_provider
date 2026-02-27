"""
Bridge routes — /api/v1/bridge/*

v2.1: Batch route is now dispatcher-driven.
/snapshot and /params are deprecated compatibility routes.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Response

from api.dependencies import get_provider
from bridge_middleware.contracts import BatchRequest
from bridge_middleware.dispatcher import dispatch_by_source

router = APIRouter(prefix="/api/v1/bridge", tags=["bridge"])

_DEPRECATED_HINT = "Deprecated endpoint. Use POST /api/bridge/batch."


def _set_deprecated_headers(response: Response) -> None:
    response.headers["Warning"] = f'299 - "{_DEPRECATED_HINT}"'
    response.headers["X-API-Deprecated"] = "true"
    response.headers["X-API-Alternative"] = "/api/bridge/batch"


@router.get("/snapshot/{symbol}", deprecated=True)
async def get_snapshot(
    response: Response,
    symbol: str,
    date: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Deprecated: use POST /api/bridge/batch with symbols=[symbol]."""
    try:
        _set_deprecated_headers(response)
        provider = get_provider()
        snap = provider.get_bridge_snapshot(symbol, date=date, source=source)
        return snap.to_dict() if hasattr(snap, "to_dict") else snap
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post(
    "/batch",
    deprecated=True,
    summary="Deprecated v1 batch route",
    description="Deprecated v1 route. Use POST /api/bridge/batch as the official downstream entrypoint.",
)
async def get_batch(req: BatchRequest) -> Dict[str, Any]:
    """
    Dispatcher-backed batch endpoint.
    NOTE: this /api/v1/bridge/batch path is deprecated; /api/bridge/batch is the official entrypoint.
    """
    try:
        provider = get_provider()
        bridge_client = getattr(provider, "_bridge", None)
        if bridge_client is None or not hasattr(bridge_client, "get_records"):
            raise RuntimeError("Bridge record client unavailable")

        # Keep records retrieval broad so dispatcher can apply date fallback correctly.
        records = bridge_client.get_records()
        if not isinstance(records, list):
            raise RuntimeError("Bridge records payload is not a list")

        result = dispatch_by_source(req, records)
        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── VA-compatible proxy routes ──────────────────────────────────────────
# These routes mirror the volatility_analysis API paths so that swing and
# vol_quant workflows can seamlessly switch their provider URL.

@router.get("/params/{symbol}", deprecated=True)
async def get_bridge_params(
    response: Response,
    symbol: str,
    date: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    Deprecated: use POST /api/bridge/batch with symbols=[symbol].
    """
    try:
        _set_deprecated_headers(response)
        provider = get_provider()
        snap = provider.get_bridge_snapshot(symbol, date=date, source=source)
        bridge_dict = snap.to_dict() if hasattr(snap, "to_dict") else snap

        return {
            "success": True,
            "symbol": symbol.upper(),
            "date": date or bridge_dict.get("as_of", ""),
            "bridge": bridge_dict,
            "requested_date": date,
            "fallback_used": False,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/micro-template/{symbol}")
async def get_micro_template(symbol: str) -> Dict[str, Any]:
    """Get micro-template selection for a symbol."""
    try:
        provider = get_provider()
        return provider.get_micro_template(symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
