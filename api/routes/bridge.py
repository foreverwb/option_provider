from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from provider.unified import UnifiedProvider


class BridgeBatchRequest(BaseModel):
    symbols: Optional[List[str]] = None
    date: Optional[str] = None
    source: str = "swing"
    min_direction_score: float = 1.0
    min_vol_score: float = 0.8
    limit: int = 50


def get_provider() -> UnifiedProvider:
    from api.app import provider

    return provider


router = APIRouter(prefix="/bridge", tags=["bridge"])


@router.get("/{symbol}")
def bridge_snapshot(
    symbol: str,
    date: Optional[str] = Query(default=None),
    unified: UnifiedProvider = Depends(get_provider),
) -> Dict[str, Any]:
    try:
        snap = unified.get_bridge_snapshot(symbol, date)
        return {"success": True, "data": snap.to_dict()}
    except Exception as exc:  # pragma: no cover - runtime guard
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/batch")
def bridge_batch(
    body: BridgeBatchRequest,
    unified: UnifiedProvider = Depends(get_provider),
) -> Dict[str, Any]:
    try:
        result = unified.get_bridge_batch(
            symbols=body.symbols,
            date=body.date,
            source=body.source,
            min_direction_score=body.min_direction_score,
            min_vol_score=body.min_vol_score,
            limit=body.limit,
        )
        return {"success": True, "data": result}
    except Exception as exc:  # pragma: no cover - runtime guard
        raise HTTPException(status_code=500, detail=str(exc)) from exc
