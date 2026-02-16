"""
Greeks Exposure command pipeline — fetch → filter → compute.
Each command function takes an OratsClient + symbol and returns a GreeksExposureResult.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models import StrikeRecord, GreeksExposureResult
from ..utils import filter_by_dte, filter_by_moneyness, find_gamma_flip
from . import calculator


# ── Command registry ────────────────────────────────────────────────────

COMMANDS = [
    "gex", "net_gex", "gex_distribution", "gex_3d",
    "dex", "net_dex", "vex", "net_vex", "vanna",
]


def _fetch_and_filter(
    client: Any,
    symbol: str,
    dte_min: int = 0,
    dte_max: int = 90,
    moneyness: float = 0.20,
) -> List[StrikeRecord]:
    """Common fetch + filter pipeline."""
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
) -> GreeksExposureResult:
    """Execute a Greeks exposure command."""
    records = _fetch_and_filter(client, symbol, dte_min, dte_max, moneyness)
    return _dispatch(command, symbol, records)


def execute_from_records(
    command: str,
    symbol: str,
    records: List[StrikeRecord],
) -> GreeksExposureResult:
    """Execute a command on pre-fetched records (useful for testing)."""
    return _dispatch(command, symbol, records)


def _dispatch(
    command: str,
    symbol: str,
    records: List[StrikeRecord],
) -> GreeksExposureResult:
    """Route to the appropriate calculator function."""
    cmd = command.lower().strip()

    if cmd == "gex":
        data = calculator.compute_gex_per_strike(records)
        net = calculator.compute_net_gex(records)
        flip = find_gamma_flip(records)
        return GreeksExposureResult(
            symbol=symbol, command=cmd,
            data={"per_strike": data},
            summary={"net_gex": net, "gamma_flip_strike": flip, "num_strikes": len(data)},
            chart_data=data,
            metadata={"unit": "$ notional"},
        )

    elif cmd == "net_gex":
        net = calculator.compute_net_gex(records)
        flip = find_gamma_flip(records)
        return GreeksExposureResult(
            symbol=symbol, command=cmd,
            data={"net_gex": net},
            summary={"net_gex": net, "gamma_flip_strike": flip},
        )

    elif cmd == "gex_distribution":
        dist = calculator.compute_gex_distribution(records)
        net = calculator.compute_net_gex(records)
        return GreeksExposureResult(
            symbol=symbol, command=cmd,
            data={"distribution": dist},
            summary={"net_gex": net, "num_strikes": len(dist)},
            chart_data=dist,
        )

    elif cmd == "gex_3d":
        matrix = calculator.compute_gex_3d(records)
        return GreeksExposureResult(
            symbol=symbol, command=cmd,
            data={"matrix": matrix},
            summary={"num_points": len(matrix)},
            chart_data=matrix,
        )

    elif cmd == "dex":
        data = calculator.compute_dex_per_strike(records)
        net = calculator.compute_net_dex(records)
        return GreeksExposureResult(
            symbol=symbol, command=cmd,
            data={"per_strike": data},
            summary={"net_dex": net, "num_strikes": len(data)},
            chart_data=data,
        )

    elif cmd == "net_dex":
        net = calculator.compute_net_dex(records)
        return GreeksExposureResult(
            symbol=symbol, command=cmd,
            data={"net_dex": net},
            summary={"net_dex": net},
        )

    elif cmd == "vex":
        data = calculator.compute_vex_per_strike(records)
        net = calculator.compute_net_vex(records)
        return GreeksExposureResult(
            symbol=symbol, command=cmd,
            data={"per_strike": data},
            summary={"net_vex": net, "num_strikes": len(data)},
            chart_data=data,
        )

    elif cmd == "net_vex":
        net = calculator.compute_net_vex(records)
        return GreeksExposureResult(
            symbol=symbol, command=cmd,
            data={"net_vex": net},
            summary={"net_vex": net},
        )

    elif cmd == "vanna":
        data = calculator.compute_vanna_per_strike(records)
        net = calculator.compute_net_vanna(records)
        return GreeksExposureResult(
            symbol=symbol, command=cmd,
            data={"per_strike": data},
            summary={"net_vanna": net, "num_strikes": len(data)},
            chart_data=data,
        )

    else:
        raise ValueError(f"Unknown Greeks command: {command}. Available: {COMMANDS}")
