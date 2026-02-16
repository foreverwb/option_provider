"""
Bridge routes — /api/v1/bridge/*
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import get_provider

router = APIRouter(prefix="/api/v1/bridge", tags=["bridge"])


class BatchRequest(BaseModel):
    symbols: List[str]
    source: Optional[str] = None
    filtering: Optional[Dict[str, Any]] = None
    sorting: Optional[Dict[str, Any]] = None


@router.get("/snapshot/{symbol}")
async def get_snapshot(symbol: str) -> Dict[str, Any]:
    """Get bridge snapshot for a single symbol."""
    try:
        provider = get_provider()
        snap = provider.get_bridge_snapshot(symbol)
        return snap.to_dict()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/batch")
async def get_batch(req: BatchRequest) -> List[Dict[str, Any]]:
    """Batch bridge snapshots."""
    try:
        provider = get_provider()
        snaps = provider.get_bridge_batch(
            req.symbols, source=req.source,
            filtering=req.filtering, sorting=req.sorting,
        )
        return [s.to_dict() for s in snaps]
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
