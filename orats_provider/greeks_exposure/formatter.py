from __future__ import annotations

from typing import Any, Dict

from ..models import ExposureResult


def exposure_result_to_dict(result: ExposureResult) -> Dict[str, Any]:
    return result.to_dict()


def exposure_chart_payload(result: ExposureResult) -> Dict[str, Any]:
    return {
        "symbol": result.symbol,
        "metric": result.metric_name,
        "spot_price": result.spot_price,
        "by_strike": result.by_strike,
        "by_expiry": result.by_expiry,
    }
