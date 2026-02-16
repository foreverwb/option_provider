"""
Greeks Exposure routes — /api/v1/greeks/{command}/{symbol}
9 commands: gex, net_gex, gex_distribution, gex_3d, dex, net_dex, vex, net_vex, vanna
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from api.dependencies import get_provider
from orats_provider.greeks_exposure.commands import COMMANDS

router = APIRouter(prefix="/api/v1/greeks", tags=["greeks"])


@router.get("/{command}/{symbol}")
async def greeks_command(
    command: str,
    symbol: str,
    dte_min: int = Query(0, ge=0),
    dte_max: int = Query(90, ge=1),
    moneyness: float = Query(0.20, ge=0.01, le=1.0),
) -> Dict[str, Any]:
    """Execute a Greeks exposure command."""
    if command not in COMMANDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown command '{command}'. Available: {COMMANDS}",
        )
    try:
        provider = get_provider()
        return provider.greeks(
            symbol, command,
            dte_min=dte_min, dte_max=dte_max, moneyness=moneyness,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
