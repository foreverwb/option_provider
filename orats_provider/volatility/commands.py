"""
Volatility analysis command pipeline — fetch → filter → analyze.
Three commands: skew, term, surface.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models import StrikeRecord, VolatilityResult
from ..utils import filter_by_dte, filter_by_moneyness
from . import analyzer


COMMANDS = ["skew", "term", "surface"]


def _fetch_and_filter(
    client: Any,
    symbol: str,
    dte_min: int = 0,
    dte_max: int = 90,
    moneyness: float = 0.20,
) -> List[StrikeRecord]:
    records = client.get_strikes(symbol)
    records = filter_by_dte(records, dte_min, dte_max)
    records = filter_by_moneyness(records, moneyness)
    return records


def execute(
    client: Any,
    symbol: str,
    command: str,
    dte_min: int = 0,
    dte_max: int = 90,
    moneyness: float = 0.20,
    **kwargs: Any,
) -> VolatilityResult:
    records = _fetch_and_filter(client, symbol, dte_min, dte_max, moneyness)
    return execute_from_records(command, symbol, records, **kwargs)


def execute_from_records(
    command: str,
    symbol: str,
    records: List[StrikeRecord],
    **kwargs: Any,
) -> VolatilityResult:
    cmd = command.lower().strip()

    if cmd == "skew":
        return _cmd_skew(symbol, records, **kwargs)
    elif cmd == "term":
        return _cmd_term(symbol, records, **kwargs)
    elif cmd == "surface":
        return _cmd_surface(symbol, records)
    else:
        raise ValueError(f"Unknown volatility command: {command}. Available: {COMMANDS}")


# ── Skew command ────────────────────────────────────────────────────────

def _cmd_skew(
    symbol: str,
    records: List[StrikeRecord],
    expiry_date: Optional[str] = None,
    **kwargs: Any,
) -> VolatilityResult:
    skew_data = analyzer.compute_skew_by_expiry(records)

    smile_data = None
    if expiry_date:
        smile_data = analyzer.compute_smile(records, expiry_date)

    avg_skew = (
        sum(d["skew"] for d in skew_data) / len(skew_data)
        if skew_data else 0
    )

    chart = smile_data if smile_data else skew_data

    return VolatilityResult(
        symbol=symbol, command="skew",
        data={"by_expiry": skew_data, "smile": smile_data},
        summary={"avg_skew": round(avg_skew, 4), "num_expiries": len(skew_data)},
        chart_data=chart,
        metadata={"expiry_date": expiry_date},
    )


# ── Term structure command ──────────────────────────────────────────────

def _cmd_term(
    symbol: str,
    records: List[StrikeRecord],
    target_dte: int = 30,
    **kwargs: Any,
) -> VolatilityResult:
    term_data = analyzer.compute_term_structure_by_expiry(records)
    contango = analyzer.detect_contango_state(term_data)
    const_iv = analyzer.compute_constant_maturity_iv(term_data, target_dte)

    return VolatilityResult(
        symbol=symbol, command="term",
        data={"by_expiry": term_data, "contango_state": contango},
        summary={
            "state": contango["state"],
            "front_iv": contango.get("front_iv"),
            "back_iv": contango.get("back_iv"),
            "ratio": contango.get("ratio"),
            f"iv_{target_dte}d": const_iv,
        },
        chart_data=term_data,
        metadata={"target_dte": target_dte},
    )


# ── Surface command ─────────────────────────────────────────────────────

def _cmd_surface(
    symbol: str,
    records: List[StrikeRecord],
) -> VolatilityResult:
    surface = analyzer.compute_vol_surface(records)

    unique_expiries = sorted(set(d["expiry_date"] for d in surface))
    unique_strikes = sorted(set(d["strike"] for d in surface))

    return VolatilityResult(
        symbol=symbol, command="surface",
        data={"surface": surface},
        summary={
            "num_points": len(surface),
            "num_expiries": len(unique_expiries),
            "num_strikes": len(unique_strikes),
        },
        chart_data=surface,
        metadata={"chart_type": "3d_surface"},
    )
