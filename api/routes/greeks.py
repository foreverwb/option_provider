from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from provider.unified import UnifiedProvider


def get_provider() -> UnifiedProvider:
    from api.app import provider

    return provider


router = APIRouter(prefix="/greeks", tags=["greeks"])


@router.get("/{command}/{symbol}")
def greeks_exposure(
    command: str,
    symbol: str,
    strikes: int = Query(default=15),
    dte: int = Query(default=98),
    expiration_filter: str = Query(default="*"),
    unified: UnifiedProvider = Depends(get_provider),
) -> Dict[str, Any]:
    valid = {"gex", "gexn", "gexr", "gexs", "dex", "dexn", "vex", "vexn", "vanna"}
    if command not in valid:
        raise HTTPException(status_code=400, detail=f"Unknown command: {command}")

    try:
        fn = getattr(unified, command)
        result = fn(symbol, strikes=strikes, dte=dte, expiration_filter=expiration_filter)
        return {"success": True, "data": result.to_dict()}
    except Exception as exc:  # pragma: no cover - runtime guard
        raise HTTPException(status_code=500, detail=str(exc)) from exc
