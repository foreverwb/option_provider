"""
Bridge routes — /api/v1/bridge/*

v2.0: Enhanced routes with full bridge batch, params endpoints.
Supports execution_state.confidence, liquidity, oi_data_available fields.
Proxy-compatible with volatility_analysis API surface.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import get_provider

router = APIRouter(prefix="/api/v1/bridge", tags=["bridge"])


class BatchRequest(BaseModel):
    symbols: Optional[List[str]] = None
    source: Optional[str] = "swing"
    date: Optional[str] = None
    min_direction_score: Optional[float] = None
    min_vol_score: Optional[float] = None
    limit: Optional[int] = None
    filtering: Optional[Dict[str, Any]] = None
    sorting: Optional[Dict[str, Any]] = None
    vix_override: Optional[float] = None


@router.get("/snapshot/{symbol}")
async def get_snapshot(
    symbol: str,
    date: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Get bridge snapshot for a single symbol."""
    try:
        provider = get_provider()
        snap = provider.get_bridge_snapshot(symbol, date=date, source=source)
        return snap.to_dict() if hasattr(snap, "to_dict") else snap
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/batch")
async def get_batch(req: BatchRequest) -> Dict[str, Any]:
    """
    Batch bridge snapshots with filtering.
    Compatible with volatility_analysis /api/bridge/batch response format.
    """
    try:
        provider = get_provider()
        result = provider.get_bridge_batch(
            symbols=req.symbols,
            source=req.source,
            date=req.date,
            min_direction_score=req.min_direction_score,
            min_vol_score=req.min_vol_score,
            limit=req.limit,
            filtering=req.filtering,
            sorting=req.sorting,
        )
        # Return VA-compatible response
        if isinstance(result, list):
            snapshots = [s.to_dict() if hasattr(s, "to_dict") else s for s in result]
            return {
                "success": True,
                "date": req.date,
                "source": req.source or "swing",
                "count": len(snapshots),
                "results": snapshots,
            }
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── VA-compatible proxy routes ──────────────────────────────────────────
# These routes mirror the volatility_analysis API paths so that swing and
# vol_quant workflows can seamlessly switch their provider URL.

@router.get("/params/{symbol}")
async def get_bridge_params(
    symbol: str,
    date: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """
    VA-compatible: GET /api/v1/bridge/params/{symbol}
    Returns bridge snapshot in the same format as VA's /api/bridge/params/<symbol>.
    """
    try:
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
