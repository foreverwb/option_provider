"""Dispatch bridge batch payloads by source with a unified response envelope."""

from __future__ import annotations

from typing import Any, Iterable

from .bridge_builder import safe_float

from .adapters.swing import to_swing_row
from .adapters.vol import to_vol_row
from .boundary_engine import compute_micro_boundary, load_boundary_rules
from .contracts import BatchError, BatchRequest, BatchResponse

_VALID_SOURCES = {"swing", "vol"}

# Module-level rule cache (loaded once).
_boundary_rules: dict[str, Any] | None = None


def _get_boundary_rules() -> dict[str, Any]:
    global _boundary_rules
    if _boundary_rules is None:
        _boundary_rules = load_boundary_rules()
    return _boundary_rules


def _record_date(record: dict[str, Any]) -> str | None:
    trade_date = record.get("trade_date")
    if isinstance(trade_date, str) and trade_date:
        return trade_date

    timestamp = record.get("timestamp")
    if isinstance(timestamp, str) and timestamp:
        return timestamp.split(" ")[0]
    return None


def _record_symbol(record: dict[str, Any]) -> str:
    symbol = record.get("symbol")
    if not isinstance(symbol, str):
        return ""
    return symbol.strip().upper()


def _available_dates(records: Iterable[dict[str, Any]]) -> list[str]:
    return sorted({d for r in records if (d := _record_date(r))}, reverse=True)


def _resolve_date(
    requested_date: str | None,
    available_dates: list[str],
    *,
    strict_date: bool = False,
) -> tuple[str | None, bool]:
    if not available_dates:
        return None, False

    if not requested_date:
        return available_dates[0], False

    if requested_date in available_dates:
        return requested_date, False

    if strict_date:
        return None, False

    # fallback to the nearest date <= requested_date
    candidates = [date for date in available_dates if date <= requested_date]
    if not candidates:
        return None, False
    return candidates[0], True


def _resolve_biases(record: dict[str, Any]) -> tuple[str, str]:
    direction_bias = record.get("direction_bias")
    vol_bias = record.get("vol_bias")
    quadrant = record.get("quadrant")

    if isinstance(quadrant, str):
        q = quadrant.replace("-", "—").replace("－", "—")
        if not isinstance(direction_bias, str) or direction_bias not in {"偏多", "偏空", "中性"}:
            if "偏多" in q:
                direction_bias = "偏多"
            elif "偏空" in q:
                direction_bias = "偏空"
            else:
                direction_bias = "中性"
        if not isinstance(vol_bias, str) or vol_bias not in {"买波", "卖波", "中性"}:
            if "买波" in q:
                vol_bias = "买波"
            elif "卖波" in q:
                vol_bias = "卖波"
            else:
                vol_bias = "中性"

    if not isinstance(direction_bias, str):
        direction_bias = "中性"
    if not isinstance(vol_bias, str):
        vol_bias = "中性"
    return direction_bias, vol_bias


def _filter_for_source(req: BatchRequest, record: dict[str, Any]) -> bool:
    direction_score = safe_float(record.get("direction_score"), 0.0)
    vol_score = safe_float(record.get("vol_score"), 0.0)
    direction_bias, vol_bias = _resolve_biases(record)

    if req.source == "swing":
        return (
            direction_bias in {"偏多", "偏空"}
            and vol_bias == "买波"
            and abs(direction_score) >= req.min_direction_score
        )
    if req.source == "vol":
        return (
            direction_bias in {"偏多", "偏空"}
            and vol_bias == "卖波"
            and abs(vol_score) >= req.min_vol_score
        )
    return False


def dispatch_by_source(req: BatchRequest, records: list[dict[str, Any]]) -> BatchResponse:
    """Dispatch records by source and return a unified batch envelope."""
    source = req.source if req.source in _VALID_SOURCES else "swing"
    errors: list[BatchError] = []

    if req.source not in _VALID_SOURCES:
        errors.append(
            BatchError(
                code="INVALID_SOURCE",
                message=f"unsupported source: {req.source}",
            )
        )
        return BatchResponse(
            success=False,
            source=source,
            requested_date=req.date,
            date=None,
            fallback_used=False,
            results=[],
            errors=errors,
        )

    dates = _available_dates(records)
    strict_date = False
    if isinstance(req.filtering, dict):
        strict_date = bool(req.filtering.get("strict_date", False))

    resolved_date, fallback_used = _resolve_date(
        req.date,
        dates,
        strict_date=strict_date,
    )
    if not resolved_date:
        errors.append(
            BatchError(
                code="NO_AVAILABLE_DATE",
                message=f"no records available for requested date={req.date}",
            )
        )
        return BatchResponse(
            success=False,
            source=source,
            requested_date=req.date,
            date=None,
            fallback_used=False,
            results=[],
            errors=errors,
        )

    dated_records = [r for r in records if _record_date(r) == resolved_date]
    wanted_symbols = req.symbols or []
    if wanted_symbols:
        by_symbol = {_record_symbol(r): r for r in dated_records if _record_symbol(r)}
        selected_records: list[dict[str, Any]] = []
        for symbol in wanted_symbols:
            rec = by_symbol.get(symbol)
            if rec is None:
                errors.append(
                    BatchError(
                        code="SYMBOL_NOT_FOUND",
                        symbol=symbol,
                        message=f"symbol {symbol} not found on {resolved_date}",
                    )
                )
                continue
            selected_records.append(rec)
    else:
        selected_records = [r for r in dated_records if _record_symbol(r)]

    filtered_records = [r for r in selected_records if _filter_for_source(req, r)]

    rows: list[dict[str, Any]] = []
    boundary_rules = _get_boundary_rules()
    for record in filtered_records:
        try:
            if source == "swing":
                row = to_swing_row(record, req)
            else:
                row = to_vol_row(record)

            # ★ Compute micro_boundary and attach to the row.
            bridge_payload = row.get("bridge", {})
            try:
                mb = compute_micro_boundary(bridge_payload, rules=boundary_rules)
                row["micro_boundary"] = mb.to_dict()
            except Exception as exc:
                # Boundary failure must never drop the row.
                row["micro_boundary"] = None
                errors.append(
                    BatchError(
                        code="BOUNDARY_COMPUTE_FAILED",
                        symbol=_record_symbol(record) or None,
                        message=str(exc),
                    )
                )

            rows.append(row)
        except Exception as exc:
            symbol = _record_symbol(record) or None
            errors.append(
                BatchError(
                    code="ROW_BUILD_FAILED",
                    symbol=symbol,
                    message=str(exc),
                )
            )

    # Stable order: symbol asc; limit at the end.
    rows = sorted(rows, key=lambda row: row.get("symbol", ""))
    if req.limit >= 0:
        rows = rows[: req.limit]

    return BatchResponse(
        success=True,
        source=source,
        requested_date=req.date,
        date=resolved_date,
        fallback_used=fallback_used,
        results=rows,
        errors=errors,
    )
