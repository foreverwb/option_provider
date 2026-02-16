"""
Greeks Exposure calculator — 9 computation functions.

GEX  = Gamma Exposure (per strike)
Net GEX = sum across all strikes
GEX Distribution = by-strike profile
GEX 3D = strike × expiry × GEX matrix
DEX  = Delta Exposure (per strike)
Net DEX = sum across all strikes
VEX  = Vega Exposure (per strike)
Net VEX = sum across all strikes
Vanna = Vanna exposure (per strike)

All functions operate on lists of StrikeRecord.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple

from ..models import StrikeRecord


# ── Contract multiplier ─────────────────────────────────────────────────

CONTRACT_MULTIPLIER = 100  # standard equity option


# ── GEX (Gamma Exposure) ───────────────────────────────────────────────

def compute_gex_per_strike(records: Sequence[StrikeRecord]) -> List[Dict[str, Any]]:
    """
    Compute GEX for each strike.
    GEX_call = gamma_call × OI_call × spot² × 0.01 × multiplier
    GEX_put  = gamma_put  × OI_put  × spot² × 0.01 × multiplier  (negative sign for dealer)
    Net GEX at strike = GEX_call - GEX_put  (dealers short puts ⇒ negative gamma)
    """
    results = []
    for r in records:
        spot2 = r.spot_price ** 2
        gex_call = r.call_gamma * r.call_oi * spot2 * 0.01 * CONTRACT_MULTIPLIER
        gex_put = -r.put_gamma * r.put_oi * spot2 * 0.01 * CONTRACT_MULTIPLIER
        net = gex_call + gex_put
        results.append({
            "strike": r.strike,
            "expiry_date": r.expiry_date,
            "dte": r.dte,
            "gex_call": round(gex_call, 2),
            "gex_put": round(gex_put, 2),
            "net_gex": round(net, 2),
            "spot_price": r.spot_price,
        })
    return results


def compute_net_gex(records: Sequence[StrikeRecord]) -> float:
    """Total net GEX across all strikes."""
    per_strike = compute_gex_per_strike(records)
    return round(sum(r["net_gex"] for r in per_strike), 2)


def compute_gex_distribution(records: Sequence[StrikeRecord]) -> List[Dict[str, Any]]:
    """GEX aggregated by strike (summed across all expiries)."""
    by_strike: Dict[float, float] = {}
    for item in compute_gex_per_strike(records):
        s = item["strike"]
        by_strike[s] = by_strike.get(s, 0) + item["net_gex"]
    return [
        {"strike": s, "net_gex": round(v, 2)}
        for s, v in sorted(by_strike.items())
    ]


def compute_gex_3d(records: Sequence[StrikeRecord]) -> List[Dict[str, Any]]:
    """GEX matrix: strike × expiry × net_gex for 3D surface."""
    return compute_gex_per_strike(records)


# ── DEX (Delta Exposure) ───────────────────────────────────────────────

def compute_dex_per_strike(records: Sequence[StrikeRecord]) -> List[Dict[str, Any]]:
    """
    DEX_call = delta_call × OI_call × spot × multiplier
    DEX_put  = delta_put  × OI_put  × spot × multiplier
    Net DEX = DEX_call + DEX_put
    """
    results = []
    for r in records:
        dex_call = r.call_delta * r.call_oi * r.spot_price * CONTRACT_MULTIPLIER
        dex_put = r.put_delta * r.put_oi * r.spot_price * CONTRACT_MULTIPLIER
        net = dex_call + dex_put
        results.append({
            "strike": r.strike,
            "expiry_date": r.expiry_date,
            "dte": r.dte,
            "dex_call": round(dex_call, 2),
            "dex_put": round(dex_put, 2),
            "net_dex": round(net, 2),
        })
    return results


def compute_net_dex(records: Sequence[StrikeRecord]) -> float:
    """Total net DEX across all strikes."""
    per_strike = compute_dex_per_strike(records)
    return round(sum(r["net_dex"] for r in per_strike), 2)


# ── VEX (Vega Exposure) ────────────────────────────────────────────────

def compute_vex_per_strike(records: Sequence[StrikeRecord]) -> List[Dict[str, Any]]:
    """
    VEX_call = vega_call × OI_call × multiplier
    VEX_put  = vega_put  × OI_put  × multiplier
    Net VEX = VEX_call + VEX_put
    """
    results = []
    for r in records:
        vex_call = r.call_vega * r.call_oi * CONTRACT_MULTIPLIER
        vex_put = r.put_vega * r.put_oi * CONTRACT_MULTIPLIER
        net = vex_call + vex_put
        results.append({
            "strike": r.strike,
            "expiry_date": r.expiry_date,
            "dte": r.dte,
            "vex_call": round(vex_call, 2),
            "vex_put": round(vex_put, 2),
            "net_vex": round(net, 2),
        })
    return results


def compute_net_vex(records: Sequence[StrikeRecord]) -> float:
    """Total net VEX across all strikes."""
    per_strike = compute_vex_per_strike(records)
    return round(sum(r["net_vex"] for r in per_strike), 2)


# ── Vanna Exposure ──────────────────────────────────────────────────────

def compute_vanna_per_strike(records: Sequence[StrikeRecord]) -> List[Dict[str, Any]]:
    """
    Vanna_call = vanna_call × OI_call × multiplier
    Vanna_put  = vanna_put  × OI_put  × multiplier
    Net Vanna = Vanna_call + Vanna_put
    """
    results = []
    for r in records:
        vanna_call = r.call_vanna * r.call_oi * CONTRACT_MULTIPLIER
        vanna_put = r.put_vanna * r.put_oi * CONTRACT_MULTIPLIER
        net = vanna_call + vanna_put
        results.append({
            "strike": r.strike,
            "expiry_date": r.expiry_date,
            "dte": r.dte,
            "vanna_call": round(vanna_call, 2),
            "vanna_put": round(vanna_put, 2),
            "net_vanna": round(net, 2),
        })
    return results


def compute_net_vanna(records: Sequence[StrikeRecord]) -> float:
    """Total net Vanna across all strikes."""
    per_strike = compute_vanna_per_strike(records)
    return round(sum(r["net_vanna"] for r in per_strike), 2)
