"""
Greeks exposure calculations.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

from ..models import StrikeRow


def _ensure_rows(strikes: Iterable[StrikeRow | Dict[str, Any]]) -> List[StrikeRow]:
    rows: List[StrikeRow] = []
    for item in strikes:
        if isinstance(item, StrikeRow):
            rows.append(item)
        elif isinstance(item, dict):
            rows.append(StrikeRow.from_orats(item))
    return rows


def _put_delta(row: StrikeRow) -> float:
    # ORATS strikes commonly expose a single delta field. Use call-delta parity.
    if row.delta <= 0.0:
        return row.delta
    if row.delta >= 1.0:
        return row.delta - 1.0
    return row.delta - 1.0


def _gamma_terms(row: StrikeRow, spot_price: float) -> Dict[str, float]:
    call_gex = float(row.call_open_interest) * float(row.gamma) * (spot_price ** 2) * 0.01
    put_gex = -1.0 * float(row.put_open_interest) * float(row.gamma) * (spot_price ** 2) * 0.01
    return {
        "call": call_gex,
        "put": put_gex,
        "net": call_gex + put_gex,
    }


def _aggregate_by_strike(rows: List[StrikeRow], fn) -> List[Dict[str, Any]]:
    grouped: Dict[float, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        strike = float(row.strike)
        values = fn(row)
        for key, val in values.items():
            grouped[strike][key] += float(val)

    out: List[Dict[str, Any]] = []
    for strike in sorted(grouped):
        item = {"strike": strike}
        item.update(grouped[strike])
        out.append(item)
    return out


def _aggregate_by_expiry(rows: List[StrikeRow], fn) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        expiry = row.expir_date
        values = fn(row)
        for key, val in values.items():
            grouped[expiry][key] += float(val)

    out: List[Dict[str, Any]] = []
    for expiry in sorted(grouped):
        item = {"expiry": expiry}
        item.update(grouped[expiry])
        out.append(item)
    return out


def _find_gamma_flip(by_strike: List[Dict[str, Any]]) -> Optional[float]:
    if not by_strike:
        return None

    for point in by_strike:
        if float(point.get("net_gex", 0.0)) == 0.0:
            return float(point["strike"])

    for prev, curr in zip(by_strike, by_strike[1:]):
        x1 = float(prev["strike"])
        x2 = float(curr["strike"])
        y1 = float(prev.get("net_gex", 0.0))
        y2 = float(curr.get("net_gex", 0.0))

        if y1 == 0.0:
            return x1
        if y2 == 0.0:
            return x2
        if y1 * y2 < 0:
            # Linear interpolation for the zero-crossing point.
            return x1 + ((0.0 - y1) * (x2 - x1) / (y2 - y1))

    return None


def compute_gamma_exposure(strikes: List[StrikeRow], spot_price: float) -> Dict[str, Any]:
    rows = _ensure_rows(strikes)

    by_strike = _aggregate_by_strike(
        rows,
        lambda row: {
            "call_gex": _gamma_terms(row, spot_price)["call"],
            "put_gex": _gamma_terms(row, spot_price)["put"],
            "net_gex": _gamma_terms(row, spot_price)["net"],
        },
    )
    by_expiry = _aggregate_by_expiry(
        rows,
        lambda row: {
            "call_gex": _gamma_terms(row, spot_price)["call"],
            "put_gex": _gamma_terms(row, spot_price)["put"],
            "net_gex": _gamma_terms(row, spot_price)["net"],
        },
    )

    total_call_gex = sum(float(r["call_gex"]) for r in by_strike)
    total_put_gex = sum(float(r["put_gex"]) for r in by_strike)
    total_gex = total_call_gex + total_put_gex

    return {
        "total_call_gex": total_call_gex,
        "total_put_gex": total_put_gex,
        "total_gex": total_gex,
        "by_strike": by_strike,
        "by_expiry": by_expiry,
    }


def compute_net_gamma(strikes: List[StrikeRow], spot_price: float) -> Dict[str, Any]:
    base = compute_gamma_exposure(strikes, spot_price)
    gamma_flip = _find_gamma_flip(base["by_strike"])
    base["gamma_flip_strike"] = gamma_flip
    return base


def compute_gamma_by_strike(strikes: List[StrikeRow], spot_price: float) -> Dict[str, Any]:
    base = compute_gamma_exposure(strikes, spot_price)
    by_strike = base["by_strike"]
    magnet = None
    if by_strike:
        magnet = max(by_strike, key=lambda row: float(row.get("net_gex", 0.0))).get("strike")
    return {
        "by_strike": by_strike,
        "total_gex": base["total_gex"],
        "magnet_strike": magnet,
    }


def compute_gamma_3d(strikes: List[StrikeRow], spot_price: float) -> Dict[str, Any]:
    rows = _ensure_rows(strikes)
    points: List[Dict[str, Any]] = []
    for row in rows:
        terms = _gamma_terms(row, spot_price)
        points.append(
            {
                "strike": row.strike,
                "expiry": row.expir_date,
                "dte": row.dte,
                "call_gex": terms["call"],
                "put_gex": terms["put"],
                "net_gex": terms["net"],
            }
        )

    points.sort(key=lambda x: (x["expiry"], x["strike"]))
    by_expiry = _aggregate_by_expiry(
        rows,
        lambda row: {
            "call_gex": _gamma_terms(row, spot_price)["call"],
            "put_gex": _gamma_terms(row, spot_price)["put"],
            "net_gex": _gamma_terms(row, spot_price)["net"],
        },
    )

    return {"points": points, "by_expiry": by_expiry}


def compute_delta_exposure(strikes: List[StrikeRow]) -> Dict[str, Any]:
    rows = _ensure_rows(strikes)

    by_strike = _aggregate_by_strike(
        rows,
        lambda row: {
            "call_dex": float(row.call_open_interest) * float(row.delta) * 100.0,
            "put_dex": float(row.put_open_interest) * _put_delta(row) * 100.0,
            "net_dex": (float(row.call_open_interest) * float(row.delta) * 100.0)
            + (float(row.put_open_interest) * _put_delta(row) * 100.0),
        },
    )

    total_call = sum(float(r["call_dex"]) for r in by_strike)
    total_put = sum(float(r["put_dex"]) for r in by_strike)

    return {
        "total_call_dex": total_call,
        "total_put_dex": total_put,
        "total_dex": total_call + total_put,
        "by_strike": by_strike,
    }


def compute_net_delta(strikes: List[StrikeRow]) -> Dict[str, Any]:
    base = compute_delta_exposure(strikes)
    base["net_dex"] = base["total_dex"]
    return base


def compute_vega_exposure(strikes: List[StrikeRow]) -> Dict[str, Any]:
    rows = _ensure_rows(strikes)

    by_strike = _aggregate_by_strike(
        rows,
        lambda row: {
            "call_vex": float(row.call_open_interest) * float(row.vega) * 100.0,
            "put_vex": float(row.put_open_interest) * float(row.vega) * 100.0,
            "total_vex": (float(row.call_open_interest) + float(row.put_open_interest))
            * float(row.vega)
            * 100.0,
        },
    )

    total_call = sum(float(r["call_vex"]) for r in by_strike)
    total_put = sum(float(r["put_vex"]) for r in by_strike)

    return {
        "total_call_vex": total_call,
        "total_put_vex": total_put,
        "total_vex": total_call + total_put,
        "by_strike": by_strike,
    }


def compute_net_vega(strikes: List[StrikeRow]) -> Dict[str, Any]:
    rows = _ensure_rows(strikes)

    by_strike = _aggregate_by_strike(
        rows,
        lambda row: {
            "call_vex": float(row.call_open_interest) * float(row.vega) * 100.0,
            "put_vex": float(row.put_open_interest) * float(row.vega) * 100.0,
            "net_vex": (float(row.call_open_interest) - float(row.put_open_interest))
            * float(row.vega)
            * 100.0,
        },
    )

    total_call = sum(float(r["call_vex"]) for r in by_strike)
    total_put = sum(float(r["put_vex"]) for r in by_strike)
    total_net = sum(float(r["net_vex"]) for r in by_strike)

    return {
        "total_call_vex": total_call,
        "total_put_vex": total_put,
        "total_net_vex": total_net,
        "by_strike": by_strike,
    }


def compute_vanna_exposure(strikes: List[StrikeRow], spot_price: float) -> Dict[str, Any]:
    rows = _ensure_rows(strikes)

    def _row_values(row: StrikeRow) -> Dict[str, float]:
        denom = spot_price if spot_price > 0 else 1.0
        vanna = (float(row.vega) / denom) * (1.0 - 2.0 * abs(float(row.delta)))
        call_exp = float(row.call_open_interest) * vanna * 100.0
        put_exp = float(row.put_open_interest) * vanna * 100.0
        return {
            "vanna": vanna,
            "call_vanna_exp": call_exp,
            "put_vanna_exp": put_exp,
            "total_vanna_exp": call_exp + put_exp,
        }

    by_strike = _aggregate_by_strike(rows, _row_values)
    total = sum(float(r["total_vanna_exp"]) for r in by_strike)

    return {
        "total_vanna_exp": total,
        "by_strike": by_strike,
    }
