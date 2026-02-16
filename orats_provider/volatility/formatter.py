from __future__ import annotations

from typing import Any, Dict

from ..models import VolatilityResult


def volatility_result_to_dict(result: VolatilityResult) -> Dict[str, Any]:
    return result.to_dict()


def volatility_chart_payload(result: VolatilityResult) -> Dict[str, Any]:
    return {
        "symbol": result.symbol,
        "metric": result.metric_name,
        "data": result.data,
    }
