"""VOL source row adapter."""

from __future__ import annotations

from typing import Any

from bridge_client.bridge_provider import parse_earnings_date_to_iso, parse_term_structure_ratio, safe_float


def _symbol_from_record(record: dict[str, Any]) -> str:
    symbol = record.get("symbol")
    if not isinstance(symbol, str):
        return ""
    return symbol.strip().upper()


def _timestamp_from_record(record: dict[str, Any]) -> str:
    timestamp = record.get("timestamp")
    if isinstance(timestamp, str):
        return timestamp
    return ""


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _maybe_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(float(text))
        except ValueError:
            return None
    return None


def _build_market_state(record: dict[str, Any], bridge: dict[str, Any]) -> dict[str, Any]:
    raw = _as_dict(record.get("raw_data"))
    existing = _as_dict(bridge.get("market_state"))
    symbol = _symbol_from_record(record)
    timestamp = _timestamp_from_record(record)
    return {
        **existing,
        "symbol": symbol or existing.get("symbol", ""),
        "as_of": timestamp or existing.get("as_of", ""),
        "vix": safe_float(_first_not_none(record.get("vix"), raw.get("VIX"), existing.get("vix")), 0.0),
        "ivr": safe_float(_first_not_none(record.get("ivr"), raw.get("IVR"), existing.get("ivr")), 0.0),
        "iv30": safe_float(_first_not_none(record.get("iv30"), raw.get("IV30"), existing.get("iv30")), 0.0),
        "hv20": safe_float(_first_not_none(record.get("hv20"), raw.get("HV20"), existing.get("hv20")), 0.0),
    }


def _build_event_state(record: dict[str, Any], bridge: dict[str, Any]) -> dict[str, Any]:
    raw = _as_dict(record.get("raw_data"))
    existing = _as_dict(bridge.get("event_state"))

    days_to_earnings = _first_not_none(
        record.get("days_to_earnings"),
        _as_dict(record.get("derived_metrics")).get("days_to_earnings"),
        existing.get("days_to_earnings"),
    )
    days_value = _maybe_int(days_to_earnings)

    earnings_date = _first_not_none(
        existing.get("earnings_date"),
        record.get("earning_date"),
        record.get("earnings_date"),
        parse_earnings_date_to_iso(raw.get("Earnings")),
    )

    return {
        **existing,
        "days_to_earnings": days_value,
        "earnings_date": earnings_date,
        "is_earnings_window": bool(
            days_value is not None and 0 <= days_value <= 14
        ),
        "is_index": bool(_first_not_none(record.get("is_index"), existing.get("is_index"), False)),
        "is_squeeze": bool(_first_not_none(record.get("is_squeeze"), existing.get("is_squeeze"), False)),
    }


def _build_execution_state(record: dict[str, Any], bridge: dict[str, Any]) -> dict[str, Any]:
    existing = _as_dict(bridge.get("execution_state"))
    field_names = [
        "quadrant",
        "direction_score",
        "vol_score",
        "direction_bias",
        "vol_bias",
        "confidence",
        "confidence_notes",
        "liquidity",
        "active_open_ratio",
        "oi_data_available",
        "data_quality",
        "trade_permission",
        "flow_bias",
        "posture_5d",
        "fear_regime",
        "dir_slope_nd",
        "dir_trend_label",
        "trend_days_used",
    ]
    out = dict(existing)
    for field in field_names:
        if field in record and record.get(field) is not None:
            out[field] = record.get(field)
    return out


def _build_term_structure(record: dict[str, Any], bridge: dict[str, Any]) -> dict[str, Any]:
    out = _as_dict(bridge.get("term_structure"))
    if isinstance(record.get("term_structure"), dict):
        out.update(record["term_structure"])

    for key, value in record.items():
        if not key.startswith("term_structure_"):
            continue
        sub_key = key[len("term_structure_") :]
        if not sub_key:
            continue
        out[sub_key] = value

    ratio = parse_term_structure_ratio(_first_not_none(out.get("ratio"), record.get("term_structure_ratio")))
    if ratio is not None:
        out["ratio"] = ratio
    return out


def build_bridge_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Build normalized bridge payload from volatility_analysis style record."""
    symbol = _symbol_from_record(record)
    timestamp = _timestamp_from_record(record)

    bridge = _as_dict(record.get("bridge"))
    market_state = _build_market_state(record, bridge)
    event_state = _build_event_state(record, bridge)
    execution_state = _build_execution_state(record, bridge)
    term_structure = _build_term_structure(record, bridge)

    out = {
        **bridge,
        "symbol": symbol,
        "as_of": timestamp,
        "market_state": market_state,
        "event_state": event_state,
        "execution_state": execution_state,
        "term_structure": term_structure,
    }
    out["ivr"] = market_state.get("ivr")
    out["iv30"] = market_state.get("iv30")
    out["hv20"] = market_state.get("hv20")
    out["earning_date"] = event_state.get("earnings_date")
    return out


def to_vol_row(record: dict[str, Any]) -> dict[str, Any]:
    """Return strict vol row shape: symbol + bridge (no market_params)."""
    symbol = _symbol_from_record(record)
    return {
        "symbol": symbol,
        "bridge": build_bridge_payload(record),
    }
