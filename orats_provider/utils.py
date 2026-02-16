"""
Utility functions for filtering and grouping option data.
"""

from __future__ import annotations

import math
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Sequence

from .models import StrikeRecord


# ── DTE filtering ───────────────────────────────────────────────────────

def filter_by_dte(
    records: Sequence[StrikeRecord],
    dte_min: int = 0,
    dte_max: int = 365,
) -> List[StrikeRecord]:
    """Keep records whose DTE is within [dte_min, dte_max]."""
    return [r for r in records if dte_min <= r.dte <= dte_max]


# ── Moneyness filtering ────────────────────────────────────────────────

def filter_by_moneyness(
    records: Sequence[StrikeRecord],
    moneyness_range: float = 0.20,
) -> List[StrikeRecord]:
    """Keep records within ±moneyness_range of spot price."""
    result = []
    for r in records:
        if r.spot_price <= 0:
            continue
        pct = abs(r.strike - r.spot_price) / r.spot_price
        if pct <= moneyness_range:
            result.append(r)
    return result


def filter_atm(
    records: Sequence[StrikeRecord],
    tolerance: float = 0.02,
) -> List[StrikeRecord]:
    """Keep only near-ATM records within tolerance of spot."""
    return [
        r for r in records
        if r.spot_price > 0 and abs(r.strike - r.spot_price) / r.spot_price <= tolerance
    ]


# ── Expiry type classification ──────────────────────────────────────────

def classify_expiry_type(expiry_date: str) -> str:
    """
    Classify an expiration date as WEEKLY, MONTHLY, or QUARTERLY.
    Monthly = 3rd Friday of month; Quarterly = month in {3,6,9,12}.
    """
    try:
        dt = _parse_date(expiry_date)
    except (ValueError, TypeError):
        return "UNKNOWN"

    # Check if 3rd Friday of month
    first_day = dt.replace(day=1)
    # weekday: Mon=0 … Fri=4
    first_friday = 1 + (4 - first_day.weekday()) % 7
    third_friday = first_friday + 14
    is_monthly = dt.day == third_friday

    if is_monthly:
        if dt.month in (3, 6, 9, 12):
            return "QUARTERLY"
        return "MONTHLY"
    return "WEEKLY"


def filter_by_expiry_type(
    records: Sequence[StrikeRecord],
    expiry_type: str,
) -> List[StrikeRecord]:
    """Keep only records matching the given expiry type (WEEKLY/MONTHLY/QUARTERLY)."""
    return [r for r in records if classify_expiry_type(r.expiry_date) == expiry_type.upper()]


# ── Contract type filtering ─────────────────────────────────────────────

def filter_calls(records: Sequence[StrikeRecord]) -> List[StrikeRecord]:
    """All records have both call/put; this is a no-op identity (for semantics)."""
    return list(records)


def filter_puts(records: Sequence[StrikeRecord]) -> List[StrikeRecord]:
    return list(records)


# ── Grouping ────────────────────────────────────────────────────────────

def group_by_expiry(records: Sequence[StrikeRecord]) -> Dict[str, List[StrikeRecord]]:
    """Group strike records by expiry_date."""
    groups: Dict[str, List[StrikeRecord]] = {}
    for r in records:
        groups.setdefault(r.expiry_date, []).append(r)
    return groups


def group_by_strike(records: Sequence[StrikeRecord]) -> Dict[float, List[StrikeRecord]]:
    """Group strike records by strike price."""
    groups: Dict[float, List[StrikeRecord]] = {}
    for r in records:
        groups.setdefault(r.strike, []).append(r)
    return groups


# ── Helpers ─────────────────────────────────────────────────────────────

def compute_dte(expiry_date: str, from_date: Optional[str] = None) -> int:
    """Compute days to expiration from a reference date (default: today)."""
    exp = _parse_date(expiry_date)
    ref = _parse_date(from_date) if from_date else date.today()
    return max(0, (exp - ref).days)


def _parse_date(s: Any) -> date:
    """Parse a date string in common formats."""
    if isinstance(s, date):
        return s
    if isinstance(s, datetime):
        return s.date()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(str(s), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s}")


def find_gamma_flip(
    records: Sequence[StrikeRecord],
) -> Optional[float]:
    """
    Find the strike price where net gamma flips from positive to negative.
    Net gamma = sum of call_gamma * call_oi - put_gamma * put_oi across OI.
    Returns the strike price of the flip point, or None if not found.
    """
    by_strike = group_by_strike(records)
    net_gammas = []
    for strike in sorted(by_strike.keys()):
        strikes = by_strike[strike]
        net_g = sum(
            (r.call_gamma * r.call_oi * 100 - r.put_gamma * r.put_oi * 100)
            for r in strikes
        )
        net_gammas.append((strike, net_g))

    # Find zero crossing
    for i in range(1, len(net_gammas)):
        prev_strike, prev_g = net_gammas[i - 1]
        curr_strike, curr_g = net_gammas[i]
        if prev_g >= 0 and curr_g < 0:
            # Linear interpolation
            if abs(prev_g - curr_g) > 1e-12:
                flip = prev_strike + (curr_strike - prev_strike) * prev_g / (prev_g - curr_g)
            else:
                flip = (prev_strike + curr_strike) / 2
            return round(flip, 2)

    return None
