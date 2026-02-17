"""
bridge_client — HTTP-based client for the Bridge API.
Fully decoupled from core modules; communicates via REST only.

v2.0: Added ExecutionState, EventState models and bridge_provider logic.
"""

from .models import (
    BridgeSnapshot,
    TermStructureSnapshot,
    ExecutionState,
    EventState,
)
from .client import BridgeClient, AsyncBridgeClient
from .micro_templates import select_micro_template, map_horizon_bias_to_dte_bias
from .bridge_provider import (
    build_bridge_response_from_record,
    extract_swing_params,
    filter_records_for_batch,
    parse_earnings_date_to_iso,
    safe_float,
    parse_term_structure_ratio,
    BRIDGE_BATCH_DEFAULT_LIMIT,
    BRIDGE_BATCH_MIN_DIRECTION_SCORE,
    BRIDGE_BATCH_MIN_VOL_SCORE,
)

__all__ = [
    "BridgeSnapshot",
    "TermStructureSnapshot",
    "ExecutionState",
    "EventState",
    "BridgeClient",
    "AsyncBridgeClient",
    "select_micro_template",
    "map_horizon_bias_to_dte_bias",
    "build_bridge_response_from_record",
    "extract_swing_params",
    "filter_records_for_batch",
    "parse_earnings_date_to_iso",
    "safe_float",
    "parse_term_structure_ratio",
    "BRIDGE_BATCH_DEFAULT_LIMIT",
    "BRIDGE_BATCH_MIN_DIRECTION_SCORE",
    "BRIDGE_BATCH_MIN_VOL_SCORE",
]
