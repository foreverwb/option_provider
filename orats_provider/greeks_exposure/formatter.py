"""
Output formatting for Greeks Exposure results.
Supports JSON, summary text, and chart-ready data structures.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from ..models import GreeksExposureResult


def to_json(result: GreeksExposureResult, indent: int = 2) -> str:
    """Serialize result to JSON string."""
    return json.dumps(result.to_dict(), indent=indent, default=str)


def to_summary(result: GreeksExposureResult) -> str:
    """Human-readable one-line summary."""
    parts = [f"[{result.command.upper()}] {result.symbol}"]
    for key, val in result.summary.items():
        if val is not None:
            if isinstance(val, float):
                parts.append(f"{key}={val:,.2f}")
            else:
                parts.append(f"{key}={val}")
    return " | ".join(parts)


def to_chart_data(result: GreeksExposureResult) -> Dict[str, Any]:
    """
    Return chart-ready structure:
    {
        "type": "bar" | "surface" | "scalar",
        "title": "...",
        "x": [...],
        "y": [...],
        "series": [...]
    }
    """
    cmd = result.command

    if cmd in ("gex", "gex_distribution", "dex", "vex", "vanna"):
        # Bar chart: strike vs exposure
        data = result.chart_data
        value_key = _value_key_for(cmd)
        return {
            "type": "bar",
            "title": f"{cmd.upper()} — {result.symbol}",
            "x": [d["strike"] for d in data],
            "y": [d.get(value_key, 0) for d in data],
            "x_label": "Strike",
            "y_label": cmd.upper(),
        }

    elif cmd == "gex_3d":
        data = result.chart_data
        return {
            "type": "surface",
            "title": f"GEX 3D — {result.symbol}",
            "data": data,
            "x_label": "Strike",
            "y_label": "DTE",
            "z_label": "Net GEX",
        }

    else:
        # Scalar commands (net_gex, net_dex, net_vex)
        return {
            "type": "scalar",
            "title": f"{cmd.upper()} — {result.symbol}",
            "value": result.summary,
        }


def _value_key_for(cmd: str) -> str:
    mapping = {
        "gex": "net_gex",
        "gex_distribution": "net_gex",
        "dex": "net_dex",
        "vex": "net_vex",
        "vanna": "net_vanna",
    }
    return mapping.get(cmd, "value")
