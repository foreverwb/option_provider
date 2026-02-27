"""SWING source row adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from bridge_client.bridge_provider import parse_term_structure_ratio, safe_float

from .vol import build_bridge_payload

if TYPE_CHECKING:
    from ..contracts import BatchRequest


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _infer_iv_path(record: dict[str, Any], bridge: dict[str, Any]) -> str:
    direct = record.get("iv_path")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    bridge_direct = bridge.get("iv_path")
    if isinstance(bridge_direct, str) and bridge_direct.strip():
        return bridge_direct.strip()

    term_structure = _as_dict(bridge.get("term_structure"))
    ratio = parse_term_structure_ratio(
        term_structure.get("ratio")
        or term_structure.get("ratio_30_90")
        or term_structure.get("term_structure_ratio")
        or record.get("term_structure_ratio")
    )
    if ratio is None:
        return "Flat"
    if ratio > 1.02:
        return "Rising"
    if ratio < 0.98:
        return "Falling"
    return "Flat"


def to_swing_row(record: dict[str, Any], req: "BatchRequest") -> dict[str, Any]:
    """Return strict swing row shape: symbol + market_params + bridge."""
    bridge = build_bridge_payload(record)
    symbol = str(bridge.get("symbol") or "").upper()
    market_state = _as_dict(bridge.get("market_state"))
    event_state = _as_dict(bridge.get("event_state"))

    vix_value = safe_float(market_state.get("vix"), 0.0)
    if req.source == "swing" and req.vix_override is not None:
        vix_value = safe_float(req.vix_override, vix_value)

    market_params = {
        "vix": vix_value,
        "ivr": safe_float(market_state.get("ivr"), 0.0),
        "iv30": safe_float(market_state.get("iv30"), 0.0),
        "hv20": safe_float(market_state.get("hv20"), 0.0),
        "iv_path": _infer_iv_path(record, bridge),
        "earning_date": event_state.get("earnings_date"),
        "beta": record.get("beta", market_state.get("beta")),
    }

    return {
        "symbol": symbol,
        "market_params": market_params,
        "bridge": bridge,
    }
