"""
Output formatting for Volatility analysis results.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from ..models import VolatilityResult


def to_json(result: VolatilityResult, indent: int = 2) -> str:
    return json.dumps(result.to_dict(), indent=indent, default=str)


def to_summary(result: VolatilityResult) -> str:
    parts = [f"[{result.command.upper()}] {result.symbol}"]
    for key, val in result.summary.items():
        if val is not None:
            if isinstance(val, float):
                parts.append(f"{key}={val:.4f}")
            else:
                parts.append(f"{key}={val}")
    return " | ".join(parts)


def to_chart_data(result: VolatilityResult) -> Dict[str, Any]:
    cmd = result.command

    if cmd == "skew":
        data = result.chart_data
        if data and "moneyness" in data[0]:
            # Smile curve
            return {
                "type": "line",
                "title": f"IV Smile — {result.symbol}",
                "x": [d["moneyness"] for d in data],
                "y": [d["mid_iv"] for d in data],
                "x_label": "Moneyness",
                "y_label": "IV",
            }
        else:
            # By-expiry skew
            return {
                "type": "bar",
                "title": f"Skew by Expiry — {result.symbol}",
                "x": [d.get("expiry_date", "") for d in data],
                "y": [d.get("skew", 0) for d in data],
                "x_label": "Expiry",
                "y_label": "Skew (Put IV - Call IV)",
            }

    elif cmd == "term":
        data = result.chart_data
        return {
            "type": "line",
            "title": f"Term Structure — {result.symbol}",
            "x": [d["dte"] for d in data],
            "y": [d["atm_iv"] for d in data],
            "x_label": "DTE",
            "y_label": "ATM IV",
            "annotations": result.summary,
        }

    elif cmd == "surface":
        return {
            "type": "surface",
            "title": f"Vol Surface — {result.symbol}",
            "data": result.chart_data,
            "x_label": "Strike",
            "y_label": "DTE",
            "z_label": "Mid IV",
        }

    return {"type": "unknown", "data": result.chart_data}
