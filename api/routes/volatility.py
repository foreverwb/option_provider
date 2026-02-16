"""
Volatility analysis routes — /api/v1/volatility/{command}/{symbol}
3 commands: skew, term, surface
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from api.dependencies import get_provider
from orats_provider.volatility.commands import COMMANDS

router = APIRouter(prefix="/api/v1/volatility", tags=["volatility"])


@router.get("/{command}/{symbol}")
async def volatility_command(
    command: str,
    symbol: str,
    dte_min: int = Query(0, ge=0),
    dte_max: int = Query(90, ge=1),
    moneyness: float = Query(0.20, ge=0.01, le=1.0),
    expiry_date: Optional[str] = Query(None),
    target_dte: int = Query(30, ge=1),
) -> Dict[str, Any]:
    """Execute a volatility analysis command."""
    if command not in COMMANDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown command '{command}'. Available: {COMMANDS}",
        )
    try:
        provider = get_provider()
        kwargs: Dict[str, Any] = {
            "dte_min": dte_min, "dte_max": dte_max, "moneyness": moneyness,
        }
        if command == "skew" and expiry_date:
            kwargs["expiry_date"] = expiry_date
        if command == "term":
            kwargs["target_dte"] = target_dte
        return provider.volatility(symbol, command, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
