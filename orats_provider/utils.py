"""
Common utility helpers for ORATS processing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from .models import ContractFilter, ExpirationFilter


def filter_by_dte(strikes: List[Dict[str, Any]], max_dte: int) -> List[Dict[str, Any]]:
    return [s for s in strikes if int(s.get("dte", 0)) <= int(max_dte)]


def filter_by_strikes_range(
    strikes: List[Dict[str, Any]],
    spot_price: float,
    num_strikes: int = 15,
) -> List[Dict[str, Any]]:
    if not strikes:
        return []

    unique_strikes = sorted({float(s.get("strike", 0.0)) for s in strikes})
    if not unique_strikes:
        return []

    atm_idx = min(range(len(unique_strikes)), key=lambda i: abs(unique_strikes[i] - spot_price))
    low = max(0, atm_idx - num_strikes)
    high = min(len(unique_strikes), atm_idx + num_strikes + 1)
    valid = set(unique_strikes[low:high])
    return [s for s in strikes if float(s.get("strike", 0.0)) in valid]


def classify_expiration(expir_date_str: str) -> str:
    dt = datetime.strptime(expir_date_str, "%Y-%m-%d")
    weekday = dt.weekday()  # Monday=0
    month = dt.month

    # Third Friday of month.
    first_day = dt.replace(day=1)
    first_friday_delta = (4 - first_day.weekday()) % 7
    first_friday = 1 + first_friday_delta
    third_friday = first_friday + 14

    is_third_friday = weekday == 4 and dt.day == third_friday
    is_quarter = month in {3, 6, 9, 12} and is_third_friday

    if is_quarter:
        return "quarterly"
    if is_third_friday:
        return "monthly"
    return "weekly"


def filter_by_expiration_type(
    strikes: List[Dict[str, Any]],
    exp_filter: ExpirationFilter,
) -> List[Dict[str, Any]]:
    if exp_filter == ExpirationFilter.ALL:
        return strikes

    if exp_filter == ExpirationFilter.WEEKLY:
        return [s for s in strikes if int(s.get("dte", 0)) <= 7]

    if exp_filter == ExpirationFilter.FRONT_DATED:
        if not strikes:
            return []
        min_dte = min(int(s.get("dte", 0)) for s in strikes)
        return [s for s in strikes if int(s.get("dte", 0)) == min_dte]

    out: List[Dict[str, Any]] = []
    for row in strikes:
        expir = row.get("expirDate")
        if not expir:
            continue
        try:
            kind = classify_expiration(str(expir))
        except ValueError:
            continue

        if exp_filter == ExpirationFilter.MONTHLY and kind == "monthly":
            out.append(row)
        elif exp_filter == ExpirationFilter.QUARTERLY and kind == "quarterly":
            out.append(row)

    return out


def parse_expiration_filter(value: str | ExpirationFilter | None) -> ExpirationFilter:
    if isinstance(value, ExpirationFilter):
        return value

    raw = str(value or "*").strip().lower()
    try:
        return ExpirationFilter(raw)
    except ValueError:
        return ExpirationFilter.ALL


def parse_contract_filter(value: str | ContractFilter | None) -> ContractFilter:
    if isinstance(value, ContractFilter):
        return value
    raw = str(value or "ntm").strip().lower()
    try:
        return ContractFilter(raw)
    except ValueError:
        return ContractFilter.NTM


def chunked_tickers(tickers: Iterable[str], chunk_size: int = 10) -> List[List[str]]:
    cleaned = [t.strip().upper() for t in tickers if isinstance(t, str) and t.strip()]
    return [cleaned[i : i + chunk_size] for i in range(0, len(cleaned), chunk_size)]


def is_atm(strike: float, spot: float, tolerance: float = 0.02) -> bool:
    if spot <= 0:
        return False
    return abs(strike - spot) / spot <= tolerance


def contract_side_value(row: Dict[str, Any], side: str, metric_key: str) -> Optional[float]:
    side = side.lower()
    metric_key = metric_key.lower()

    if metric_key == "iv":
        metric_key = "midiv"

    if side == "calls":
        mapping = {
            "midiv": row.get("callMidIv"),
            "bidiv": row.get("callBidIv"),
            "askiv": row.get("callAskIv"),
            "value": row.get("callValue"),
        }
        return _to_optional_float(mapping.get(metric_key))

    if side == "puts":
        mapping = {
            "midiv": row.get("putMidIv"),
            "bidiv": row.get("putBidIv"),
            "askiv": row.get("putAskIv"),
            "value": row.get("putValue"),
        }
        return _to_optional_float(mapping.get(metric_key))

    return None


def _to_optional_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
