"""
Bridge provider — decoupled business logic from volatility_analysis/api_extension.py.

This module provides all the bridge snapshot construction, batch filtering,
and swing-params extraction logic that was previously coupled to the VA Flask app.
It operates purely on dict-based records and has zero imports from VA core modules.

Consumers: options_provider API routes, unified provider.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .models import BridgeSnapshot, ExecutionState, EventState

# ── Constants (migrated from core/api_constants.py) ─────────────────────
BRIDGE_BATCH_DEFAULT_LIMIT = 50
# Keep aligned with VA's decision gate:
# direction_pref_threshold(0.50) + neutral_buffer(0.05) = 0.55.
BRIDGE_BATCH_MIN_DIRECTION_SCORE = 0.55
# Keep aligned with VA vol decision gate:
# vol_pref_threshold(0.07) + max(0.07*0.25, 0.05) = 0.12.
BRIDGE_BATCH_MIN_VOL_SCORE = 0.12


# ── Utility helpers ─────────────────────────────────────────────────────

def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return default


def parse_earnings_date_to_iso(earnings_str: Optional[str]) -> Optional[str]:
    """
    Convert earnings date string to ISO format (YYYY-MM-DD).
    Input: "22-Oct-2025 BMO" or "19-Nov-2025 AMC"
    Output: "2025-10-22"
    """
    if not earnings_str or not isinstance(earnings_str, str):
        return None

    t = earnings_str.strip()
    parts = t.split()
    if len(parts) >= 2 and parts[-1] in ("AMC", "BMO"):
        t = " ".join(parts[:-1])
    t = t.replace("  ", " ")

    for fmt in ("%d-%b-%Y", "%d %b %Y", "%d-%b-%y", "%d %b %y"):
        try:
            dt = datetime.strptime(t, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_term_structure_ratio(value: Any) -> Optional[float]:
    """Parse term structure ratio from various formats."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.upper() == "N/A":
        return None
    try:
        return float(text.split()[0])
    except (TypeError, ValueError, IndexError):
        return None


# ── Bridge Snapshot construction ────────────────────────────────────────

def build_bridge_response_from_record(
    record: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a bridge snapshot dict from a VA record.
    This is the decoupled version of _build_bridge_snapshot_for_record
    from api_extension.py.

    If the record already contains a 'bridge' key, it is used directly.
    Otherwise, a bridge-compatible dict is assembled from record fields.
    """
    bridge_data = record.get("bridge")

    if bridge_data:
        if hasattr(bridge_data, "to_dict"):
            bridge_data = bridge_data.to_dict()
    else:
        # Rebuild from flat record fields
        bridge_data = _assemble_bridge_from_flat_record(record)

    # Ensure convenience fields are populated
    if isinstance(bridge_data, dict):
        bridge_data = dict(bridge_data)
        market_state = bridge_data.get("market_state", {}) if isinstance(bridge_data.get("market_state"), dict) else {}
        event_state = bridge_data.get("event_state", {}) if isinstance(bridge_data.get("event_state"), dict) else {}
        bridge_data.setdefault("ivr", market_state.get("ivr"))
        bridge_data.setdefault("iv30", market_state.get("iv30"))
        bridge_data.setdefault("hv20", market_state.get("hv20"))
        bridge_data.setdefault("earning_date", event_state.get("earnings_date"))

    return bridge_data


def _assemble_bridge_from_flat_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble a bridge-like dict from flat VA record fields."""
    raw = record.get("raw_data") or {}

    symbol = (record.get("symbol") or raw.get("Symbol") or "").upper()
    as_of = record.get("timestamp", "")
    if isinstance(as_of, str) and " " in as_of:
        as_of = as_of.split(" ")[0]

    ivr = safe_float(record.get("ivr") or raw.get("IVR"), 0.0)
    iv30 = safe_float(record.get("iv30") or raw.get("IV30"), 0.0)
    hv20 = safe_float(record.get("hv20") or raw.get("HV20"), 0.0)
    vix = safe_float(record.get("vix") or raw.get("VIX"), 0.0)

    market_state = {
        "symbol": symbol,
        "as_of": as_of,
        "vix": vix,
        "ivr": ivr,
        "iv30": iv30,
        "hv20": hv20,
    }

    earnings_raw = raw.get("Earnings")
    earnings_iso = parse_earnings_date_to_iso(earnings_raw)
    days_to_earnings = record.get("days_to_earnings")

    event_state = {
        "earnings_date": earnings_iso,
        "days_to_earnings": days_to_earnings,
        "is_earnings_window": (
            isinstance(days_to_earnings, (int, float))
            and 0 <= days_to_earnings <= 14
        ),
        "is_index": bool(record.get("is_index", False)),
        "is_squeeze": bool(record.get("is_squeeze", False)),
    }

    execution_state = {
        "quadrant": record.get("quadrant"),
        "direction_score": safe_float(record.get("direction_score"), 0.0),
        "vol_score": safe_float(record.get("vol_score"), 0.0),
        "direction_bias": record.get("direction_bias"),
        "vol_bias": record.get("vol_bias"),
        "confidence": record.get("confidence"),
        "confidence_notes": record.get("confidence_notes"),
        "liquidity": record.get("liquidity"),
        "active_open_ratio": safe_float(record.get("active_open_ratio"), 0.0),
        "oi_data_available": record.get("oi_data_available"),
        "data_quality": record.get("data_quality"),
        "trade_permission": record.get("trade_permission"),
        "flow_bias": safe_float(record.get("flow_bias"), 0.0),
        "posture_5d": record.get("posture_5d"),
        "fear_regime": record.get("fear_regime"),
    }

    return {
        "symbol": symbol,
        "as_of": as_of,
        "market_state": market_state,
        "event_state": event_state,
        "execution_state": execution_state,
        "term_structure": record.get("term_structure"),
    }


# ── Swing params extraction ─────────────────────────────────────────────

def extract_swing_params(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract swing/micro system parameters from a VA analysis record.
    Decoupled from api_extension.py.
    """
    raw_data = record.get("raw_data", {})
    derived_metrics = record.get("derived_metrics", {})

    ivr = record.get("ivr") or raw_data.get("IVR")
    iv30 = record.get("iv30") or raw_data.get("IV30")
    hv20 = record.get("hv20") or raw_data.get("HV20")
    earnings_raw = raw_data.get("Earnings")
    vix = record.get("vix")
    if vix is None:
        vix = record.get("dynamic_params", {}).get("vix")

    def clean_number(val):
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        try:
            return float(str(val).replace(",", "").replace("%", ""))
        except Exception:
            return None

    term_structure_raw = record.get("term_structure_ratio", "N/A")
    term_structure_ratio = parse_term_structure_ratio(term_structure_raw)

    return {
        "vix": clean_number(vix),
        "ivr": clean_number(ivr),
        "iv30": clean_number(iv30),
        "hv20": clean_number(hv20),
        "earning_date": parse_earnings_date_to_iso(earnings_raw),
        "_source": {
            "symbol": record.get("symbol"),
            "timestamp": record.get("timestamp"),
            "quadrant": record.get("quadrant"),
            "confidence": record.get("confidence"),
            "direction_score": record.get("direction_score", 0.0),
            "vol_score": record.get("vol_score", 0.0),
            "direction_bias": record.get("direction_bias", "中性"),
            "vol_bias": record.get("vol_bias", "中性"),
            "is_squeeze": record.get("is_squeeze", False),
            "is_index": record.get("is_index", False),
            "spot_vol_corr_score": record.get("spot_vol_corr_score", 0.0),
            "term_structure_ratio": term_structure_ratio,
            "ivrv_ratio": derived_metrics.get("ivrv_ratio", 1.0),
            "regime_ratio": derived_metrics.get("regime_ratio", 1.0),
            "days_to_earnings": derived_metrics.get("days_to_earnings"),
        },
    }


# ── Batch filtering ─────────────────────────────────────────────────────

def filter_records_for_batch(
    records: List[Dict[str, Any]],
    source: str = "swing",
    symbols_set: Optional[set] = None,
    min_direction_score: float = BRIDGE_BATCH_MIN_DIRECTION_SCORE,
    min_vol_score: float = BRIDGE_BATCH_MIN_VOL_SCORE,
    limit: int = BRIDGE_BATCH_DEFAULT_LIMIT,
) -> List[Dict[str, Any]]:
    """
    Filter and sort records for bridge batch response.
    Implements the same logic as api_extension.py register_bridge_api's get_bridge_batch.
    """
    results: List[Dict[str, Any]] = []

    for record in records:
        symbol = (record.get("symbol") or "").upper()
        if not symbol:
            continue
        if symbols_set is not None and symbol not in symbols_set:
            continue

        direction_score = safe_float(record.get("direction_score"), 0.0)
        vol_score = safe_float(record.get("vol_score"), 0.0)
        direction_bias = record.get("direction_bias", "中性")
        vol_bias = record.get("vol_bias", "中性")

        if source == "swing":
            if direction_bias not in {"偏多", "偏空"}:
                continue
            if vol_bias != "买波":
                continue
            if abs(direction_score) < min_direction_score:
                continue
        elif source == "vol":
            if direction_bias not in {"偏多", "偏空"}:
                continue
            if vol_bias != "卖波":
                continue
            if abs(vol_score) < min_vol_score:
                continue
        else:
            if abs(direction_score) < min_direction_score:
                continue

        bridge_data = build_bridge_response_from_record(record)

        derived_metrics = record.get("derived_metrics") if isinstance(record.get("derived_metrics"), dict) else {}
        ivrv_ratio = safe_float(derived_metrics.get("ivrv_ratio", 1.0), 1.0)

        results.append({
            "symbol": symbol,
            "timestamp": record.get("timestamp"),
            "quadrant": record.get("quadrant"),
            "direction_score": direction_score,
            "vol_score": vol_score,
            "direction_bias": direction_bias,
            "vol_bias": vol_bias,
            "confidence": record.get("confidence"),
            "term_structure_ratio": parse_term_structure_ratio(record.get("term_structure_ratio")),
            "ivrv_ratio": ivrv_ratio,
            "bridge": bridge_data,
        })

    # Sort
    if source == "vol":
        results.sort(key=lambda item: abs(safe_float(item.get("vol_score"), 0.0)), reverse=True)
    else:
        results.sort(key=lambda item: abs(safe_float(item.get("direction_score"), 0.0)), reverse=True)

    return results[:limit]
