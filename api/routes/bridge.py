"""
Bridge routes — /api/v1/bridge/*

v2.1: Batch route is now dispatcher-driven.
v2.2: Structured terminal logging for batch calls.
/snapshot and /params are deprecated compatibility routes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Response

from api.dependencies import get_provider
from bridge_provider.contracts import BatchRequest, BatchResponse
from bridge_provider.dispatcher import dispatch_by_source

router = APIRouter(prefix="/api/v1/bridge", tags=["bridge"])

_batch_logger = logging.getLogger("options_provider.bridge_batch")
_batch_logger.setLevel(logging.INFO)
_batch_logger.propagate = False
if not _batch_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.INFO)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _batch_logger.addHandler(_handler)

_SOURCE_LABELS = {"swing": "波段", "vol": "波动率"}


def _log_batch_result(req: BatchRequest, resp: BatchResponse) -> None:
    """Emit a structured terminal log block after a bridge batch dispatch."""
    source_label = _SOURCE_LABELS.get(resp.source, resp.source)
    source_str = f"{resp.source} ({source_label})"

    # Date info
    fallback_tag = "yes" if resp.fallback_used else "no"
    if resp.date:
        date_str = f"{resp.date} (requested: {req.date or 'latest'}, fallback: {fallback_tag})"
    else:
        date_str = f"none (requested: {req.date or 'latest'})"

    # Symbols in
    if req.symbols:
        symbols_in_str = f"{req.symbols}   ({len(req.symbols)})"
    else:
        symbols_in_str = "* (all)"

    # Symbols out
    out_symbols: List[str] = [r.get("symbol", "?") if isinstance(r, dict) else getattr(r, "symbol", "?") for r in resp.results]
    if out_symbols:
        symbols_out_str = f"{out_symbols}   ({len(out_symbols)})"
    else:
        symbols_out_str = "[]   (0)"

    # Filters
    filters_str = f"min_dir={req.min_direction_score}  min_vol={req.min_vol_score}  limit={req.limit}"

    # Errors
    error_count = len(resp.errors)
    if error_count > 0:
        error_summaries = [
            f"{e.code}: {e.symbol}" if e.symbol else (e.code or e.message)
            for e in resp.errors
        ]
        errors_str = f"{error_count} → [{', '.join(error_summaries)}]"
    else:
        errors_str = "0"

    status_str = "✓ success" if resp.success else "✗ failed"

    _batch_logger.info(
        "\n"
        "──── Bridge Batch ────────────────────────────────────\n"
        "  source     : %s\n"
        "  date       : %s\n"
        "  symbols_in : %s\n"
        "  symbols_out: %s\n"
        "  filters    : %s\n"
        "  errors     : %s\n"
        "  status     : %s\n"
        "──────────────────────────────────────────────────────",
        source_str,
        date_str,
        symbols_in_str,
        symbols_out_str,
        filters_str,
        errors_str,
        status_str,
    )

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
        _log_batch_result(req, result)
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