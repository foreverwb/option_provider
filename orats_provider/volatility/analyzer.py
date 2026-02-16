"""
Volatility analytics helpers.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Dict, List

from ..models import ContractFilter, StrikeRow, VolMetric
from ..utils import is_atm, parse_contract_filter


def _spot(rows: List[StrikeRow]) -> float:
    if not rows:
        return 0.0
    return float(rows[0].spot_price or rows[0].stock_price or 0.0)


def _metric_value(row: StrikeRow, metric: str) -> float:
    normalized = str(metric or VolMetric.VOLATILITY_MID.name).strip().upper()
    if normalized in {"VOLATILITY_MID", "SMVVOL"}:
        return float(row.smv_vol)
    if normalized in {"IV", "IVMID"}:
        vals = [row.call_mid_iv, row.put_mid_iv]
        vals = [float(v) for v in vals if v is not None]
        return mean(vals) if vals else 0.0
    if normalized in {"IVASK", "IV_ASK"}:
        vals = [row.call_ask_iv, row.put_ask_iv]
        vals = [float(v) for v in vals if v is not None]
        return mean(vals) if vals else 0.0
    if normalized == "DELTA":
        return float(row.delta)
    if normalized == "GAMMA":
        return float(row.gamma)
    if normalized == "VEGA":
        return float(row.vega)
    if normalized == "RHO":
        return float(row.rho)
    return float(row.smv_vol)


def _filter_rows_for_contract(rows: List[StrikeRow], contract_filter: str) -> List[StrikeRow]:
    filt = parse_contract_filter(contract_filter)
    if filt in {ContractFilter.CALLS, ContractFilter.PUTS}:
        return rows

    spot = _spot(rows)
    if spot <= 0:
        return rows

    if filt == ContractFilter.ATM:
        return [r for r in rows if is_atm(r.strike, spot)]

    if filt == ContractFilter.NTM:
        return [r for r in rows if abs(r.strike - spot) / spot <= 0.05]

    if filt == ContractFilter.ITM:
        return [r for r in rows if abs(r.strike - spot) / spot > 0.02]

    return rows


def analyze_skew(
    rows: List[StrikeRow],
    summaries: Dict[str, Any] | None = None,
    contract_filter: str = "ntm",
) -> Dict[str, Any]:
    summaries = summaries or {}
    filtered = _filter_rows_for_contract(rows, contract_filter)
    grouped: Dict[str, List[StrikeRow]] = defaultdict(list)
    for row in filtered:
        grouped[row.expir_date].append(row)

    by_expiry: List[Dict[str, Any]] = []
    for expiry, items in grouped.items():
        call_vals = [float(r.call_mid_iv) for r in items]
        put_vals = [float(r.put_mid_iv) for r in items]
        call_iv = mean(call_vals) if call_vals else 0.0
        put_iv = mean(put_vals) if put_vals else 0.0
        skew_val = put_iv - call_iv
        by_expiry.append(
            {
                "expiry": expiry,
                "count": len(items),
                "call_iv": call_iv,
                "put_iv": put_iv,
                "skew": skew_val,
            }
        )

    by_expiry.sort(key=lambda x: x["expiry"])
    overall_skew = mean([item["skew"] for item in by_expiry]) if by_expiry else 0.0

    return {
        "overall_skew": overall_skew,
        "by_expiry": by_expiry,
        "summary_skewing": summaries.get("skewing"),
        "summary_contango": summaries.get("contango"),
        "summary_iv30d": summaries.get("iv30d"),
        "summary_iv60d": summaries.get("iv60d"),
        "summary_iv90d": summaries.get("iv90d"),
        "summary_delta_wing": {
            "dlt5Iv30d": summaries.get("dlt5Iv30d"),
            "dlt25Iv30d": summaries.get("dlt25Iv30d"),
            "dlt75Iv30d": summaries.get("dlt75Iv30d"),
            "dlt95Iv30d": summaries.get("dlt95Iv30d"),
        },
    }


def analyze_term_structure(
    summaries: Dict[str, Any] | None,
    monies: List[Dict[str, Any]],
) -> Dict[str, Any]:
    summaries = summaries or {}

    constant_curve = {
        "iv10d": summaries.get("iv10d"),
        "iv20d": summaries.get("iv20d"),
        "iv30d": summaries.get("iv30d"),
        "iv60d": summaries.get("iv60d"),
        "iv90d": summaries.get("iv90d"),
        "iv6m": summaries.get("iv6m"),
        "iv1y": summaries.get("iv1y"),
        "exErnIv30d": summaries.get("exErnIv30d"),
        "exErnIv60d": summaries.get("exErnIv60d"),
        "exErnIv90d": summaries.get("exErnIv90d"),
    }

    implied_curve = []
    for row in monies:
        implied_curve.append(
            {
                "expiry": row.get("expirDate"),
                "dte": row.get("dte"),
                "atmiv": row.get("atmiv"),
                "slope": row.get("slope"),
                "calVol": row.get("calVol"),
            }
        )
    implied_curve.sort(key=lambda x: (x.get("dte") if x.get("dte") is not None else 99999))

    iv30 = _float_or_none(summaries.get("iv30d"))
    iv60 = _float_or_none(summaries.get("iv60d"))
    iv90 = _float_or_none(summaries.get("iv90d"))
    contango_raw = _float_or_none(summaries.get("contango"))

    if contango_raw is not None:
        state = "contango" if contango_raw > 0 else "backwardation"
    elif iv30 is not None and iv60 is not None and iv90 is not None:
        if iv30 <= iv60 <= iv90:
            state = "contango"
        elif iv30 >= iv60 >= iv90:
            state = "backwardation"
        else:
            state = "mixed"
    else:
        state = "unknown"

    return {
        "constant_curve": constant_curve,
        "implied_curve": implied_curve,
        "forward_curve": {
            "fwd30_20": summaries.get("fwd30_20"),
            "fwd60_30": summaries.get("fwd60_30"),
            "fwd90_30": summaries.get("fwd90_30"),
            "fwd90_60": summaries.get("fwd90_60"),
            "fwd180_90": summaries.get("fwd180_90"),
        },
        "state": state,
        "contango": summaries.get("contango"),
    }


def analyze_surface(
    rows: List[StrikeRow],
    metric: str = "VOLATILITY_MID",
    contract_filter: str = "ntm",
) -> Dict[str, Any]:
    filtered = _filter_rows_for_contract(rows, contract_filter)

    expiries = sorted({r.expir_date for r in filtered})
    strikes = sorted({float(r.strike) for r in filtered})

    point_map: Dict[tuple[str, float], List[float]] = defaultdict(list)
    points: List[Dict[str, Any]] = []

    for row in filtered:
        value = _metric_value(row, metric)
        key = (row.expir_date, float(row.strike))
        point_map[key].append(value)
        points.append(
            {
                "expiry": row.expir_date,
                "strike": float(row.strike),
                "dte": row.dte,
                "value": value,
            }
        )

    matrix: List[List[float | None]] = []
    for expiry in expiries:
        row_values: List[float | None] = []
        for strike in strikes:
            vals = point_map.get((expiry, strike), [])
            row_values.append(mean(vals) if vals else None)
        matrix.append(row_values)

    points.sort(key=lambda x: (x["expiry"], x["strike"]))
    return {
        "metric": metric,
        "expiries": expiries,
        "strikes": strikes,
        "matrix": matrix,
        "points": points,
    }


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
