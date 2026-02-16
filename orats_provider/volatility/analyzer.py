"""
Volatility analysis functions — skew, term structure, and surface.

Skew:
  - by-expiry skew (put IV - call IV slope)
  - smile curve (IV vs strike for a single expiry)

Term Structure:
  - constant-maturity interpolation
  - by-expiry ATM IV
  - contango/backwardation state detection

Surface:
  - strike × expiry IV matrix
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..models import StrikeRecord, MoniesRecord
from ..utils import group_by_expiry, filter_atm


# ── Skew Analysis ───────────────────────────────────────────────────────

def compute_skew_by_expiry(records: Sequence[StrikeRecord]) -> List[Dict[str, Any]]:
    """
    Compute skew per expiry as the slope of put IV vs call IV
    across strikes.  Approximated as:
    skew = avg(put_iv) - avg(call_iv) for OTM options.
    """
    by_exp = group_by_expiry(list(records))
    results = []
    for expiry in sorted(by_exp.keys()):
        strikes = by_exp[expiry]
        if not strikes:
            continue
        spot = strikes[0].spot_price
        # OTM puts: strike < spot, OTM calls: strike > spot
        otm_put_ivs = [r.put_iv for r in strikes if r.strike < spot and r.put_iv > 0]
        otm_call_ivs = [r.call_iv for r in strikes if r.strike > spot and r.call_iv > 0]

        avg_put = sum(otm_put_ivs) / len(otm_put_ivs) if otm_put_ivs else 0
        avg_call = sum(otm_call_ivs) / len(otm_call_ivs) if otm_call_ivs else 0
        skew = avg_put - avg_call

        results.append({
            "expiry_date": expiry,
            "dte": strikes[0].dte,
            "avg_put_iv": round(avg_put, 4),
            "avg_call_iv": round(avg_call, 4),
            "skew": round(skew, 4),
            "num_strikes": len(strikes),
        })
    return results


def compute_smile(
    records: Sequence[StrikeRecord],
    expiry_date: str,
) -> List[Dict[str, Any]]:
    """
    IV smile curve for a single expiry: IV vs strike.
    Returns midpoint IV = (call_iv + put_iv) / 2 at each strike.
    """
    filtered = [r for r in records if r.expiry_date == expiry_date]
    results = []
    for r in sorted(filtered, key=lambda x: x.strike):
        mid_iv = (r.call_iv + r.put_iv) / 2 if (r.call_iv > 0 and r.put_iv > 0) else max(r.call_iv, r.put_iv)
        moneyness = (r.strike / r.spot_price - 1) if r.spot_price > 0 else 0
        results.append({
            "strike": r.strike,
            "moneyness": round(moneyness, 4),
            "call_iv": round(r.call_iv, 4),
            "put_iv": round(r.put_iv, 4),
            "mid_iv": round(mid_iv, 4),
        })
    return results


# ── Term Structure Analysis ─────────────────────────────────────────────

def compute_term_structure_by_expiry(
    records: Sequence[StrikeRecord],
    atm_tolerance: float = 0.02,
) -> List[Dict[str, Any]]:
    """
    ATM IV term structure: ATM IV for each expiry.
    """
    by_exp = group_by_expiry(list(records))
    results = []
    for expiry in sorted(by_exp.keys()):
        strikes = by_exp[expiry]
        atm = filter_atm(strikes, tolerance=atm_tolerance)
        if not atm:
            continue
        avg_iv = sum((r.call_iv + r.put_iv) / 2 for r in atm) / len(atm)
        results.append({
            "expiry_date": expiry,
            "dte": atm[0].dte,
            "atm_iv": round(avg_iv, 4),
            "num_atm_strikes": len(atm),
        })
    return results


def compute_constant_maturity_iv(
    term_data: List[Dict[str, Any]],
    target_dte: int = 30,
) -> Optional[float]:
    """
    Interpolate ATM IV for a constant maturity (e.g. 30-day).
    Linear interpolation between nearest bracketing expiries.
    """
    if not term_data:
        return None

    sorted_data = sorted(term_data, key=lambda x: x["dte"])

    # Exact match
    for d in sorted_data:
        if d["dte"] == target_dte:
            return d["atm_iv"]

    # Find bracketing expiries
    lower = None
    upper = None
    for d in sorted_data:
        if d["dte"] < target_dte:
            lower = d
        elif d["dte"] > target_dte and upper is None:
            upper = d

    if lower and upper:
        # Linear interpolation
        w = (target_dte - lower["dte"]) / (upper["dte"] - lower["dte"])
        iv = lower["atm_iv"] + w * (upper["atm_iv"] - lower["atm_iv"])
        return round(iv, 4)

    # Extrapolation fallback
    if lower:
        return lower["atm_iv"]
    if upper:
        return upper["atm_iv"]
    return None


def detect_contango_state(term_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Determine term structure state:
    - CONTANGO: front < back (normal)
    - BACKWARDATION: front > back (inverted)
    - FLAT: approximately equal
    """
    if len(term_data) < 2:
        return {"state": "UNKNOWN", "front_iv": None, "back_iv": None, "ratio": None}

    sorted_data = sorted(term_data, key=lambda x: x["dte"])
    front = sorted_data[0]
    back = sorted_data[-1]

    front_iv = front["atm_iv"]
    back_iv = back["atm_iv"]
    ratio = front_iv / back_iv if back_iv > 0 else 1.0

    FLAT_THRESHOLD = 0.05  # ±5%

    if ratio < (1 - FLAT_THRESHOLD):
        state = "CONTANGO"
    elif ratio > (1 + FLAT_THRESHOLD):
        state = "BACKWARDATION"
    else:
        state = "FLAT"

    return {
        "state": state,
        "front_iv": round(front_iv, 4),
        "front_dte": front["dte"],
        "back_iv": round(back_iv, 4),
        "back_dte": back["dte"],
        "ratio": round(ratio, 4),
    }


# ── Surface Analysis ───────────────────────────────────────────────────

def compute_vol_surface(records: Sequence[StrikeRecord]) -> List[Dict[str, Any]]:
    """
    Build a volatility surface matrix: strike × expiry → IV.
    Returns list of {strike, expiry_date, dte, call_iv, put_iv, mid_iv}.
    """
    results = []
    for r in records:
        mid_iv = (r.call_iv + r.put_iv) / 2 if (r.call_iv > 0 and r.put_iv > 0) else max(r.call_iv, r.put_iv)
        moneyness = (r.strike / r.spot_price - 1) if r.spot_price > 0 else 0
        results.append({
            "strike": r.strike,
            "moneyness": round(moneyness, 4),
            "expiry_date": r.expiry_date,
            "dte": r.dte,
            "call_iv": round(r.call_iv, 4),
            "put_iv": round(r.put_iv, 4),
            "mid_iv": round(mid_iv, 4),
        })
    return sorted(results, key=lambda x: (x["dte"], x["strike"]))
