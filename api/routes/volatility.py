from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from provider.unified import UnifiedProvider


def get_provider() -> UnifiedProvider:
    from api.app import provider

    return provider


router = APIRouter(prefix="/volatility", tags=["volatility"])


@router.get("/{command}/{symbol}")
def volatility(
    command: str,
    symbol: str,
    metric: str = Query(default="VOLATILITY_MID"),
    contract_filter: str = Query(default="ntm"),
    dte: int = Query(default=98),
    expiration_filter: str = Query(default="*"),
    unified: UnifiedProvider = Depends(get_provider),
) -> Dict[str, Any]:
    valid = {"skew", "term", "surface"}
    if command not in valid:
        raise HTTPException(status_code=400, detail=f"Unknown command: {command}")

    try:
        fn = getattr(unified, command)
        result = fn(
            symbol,
            metric=metric,
            contract_filter=contract_filter,
            dte=dte,
            expiration_filter=expiration_filter,
        )
        return {"success": True, "data": result.to_dict()}
    except TypeError:
        # term() does not use metric/contract_filter in this implementation.
        try:
            fn = getattr(unified, command)
            result = fn(symbol, dte=dte, expiration_filter=expiration_filter)
            return {"success": True, "data": result.to_dict()}
        except Exception as exc:  # pragma: no cover - runtime guard
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - runtime guard
        raise HTTPException(status_code=500, detail=str(exc)) from exc
