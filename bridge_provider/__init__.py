"""
bridge_provider — Bridge API client, middleware, and micro boundary engine.

Merged from bridge_client + bridge_middleware packages.
Provides: HTTP client, data models, batch dispatch, and boundary computation.

v2.0: Added ExecutionState, EventState models and bridge builder logic.
v3.0: Added MicroBoundary dataclass family + boundary_engine for centralized
      boundary decisions.
v4.0: Merged bridge_client + bridge_middleware into unified bridge_provider.
"""

# ── Models ──────────────────────────────────────────────────────────────
from .models import (
    BridgeSnapshot,
    TermStructureSnapshot,
    ExecutionState,
    EventState,
    MicroBoundary,
    BaseBoundary,
    DirectionalRange,
    VolRange,
    LiquidityBoundary,
    OIAvailability,
    ConfidenceBoundary,
    TemporalBoundary,
    TermStructureBoundary,
    SwingOverlay,
    VolQuantOverlay,
    StrategyOverlay,
    Degradation,
    BoundaryMetadata,
)

# ── Client ──────────────────────────────────────────────────────────────
from .client import BridgeClient, AsyncBridgeClient

# ── Micro templates ─────────────────────────────────────────────────────
from .micro_templates import select_micro_template, map_horizon_bias_to_dte_bias

# ── Bridge builder (formerly bridge_provider.py) ────────────────────────
from .bridge_builder import (
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

# ── Contracts ───────────────────────────────────────────────────────────
from .contracts import (
    BatchError,
    BatchRequest,
    BatchResponse,
    SwingBatchRow,
    SwingMarketParams,
    VolBatchRow,
)

# ── Dispatcher ──────────────────────────────────────────────────────────
from .dispatcher import dispatch_by_source

# ── Boundary engine ────────────────────────────────────────────────────
from .boundary_engine import compute_micro_boundary, load_boundary_rules

__all__ = [
    # Models
    "BridgeSnapshot",
    "TermStructureSnapshot",
    "ExecutionState",
    "EventState",
    "MicroBoundary",
    "BaseBoundary",
    "DirectionalRange",
    "VolRange",
    "LiquidityBoundary",
    "OIAvailability",
    "ConfidenceBoundary",
    "TemporalBoundary",
    "TermStructureBoundary",
    "SwingOverlay",
    "VolQuantOverlay",
    "StrategyOverlay",
    "Degradation",
    "BoundaryMetadata",
    # Client
    "BridgeClient",
    "AsyncBridgeClient",
    # Micro templates
    "select_micro_template",
    "map_horizon_bias_to_dte_bias",
    # Bridge builder
    "build_bridge_response_from_record",
    "extract_swing_params",
    "filter_records_for_batch",
    "parse_earnings_date_to_iso",
    "safe_float",
    "parse_term_structure_ratio",
    "BRIDGE_BATCH_DEFAULT_LIMIT",
    "BRIDGE_BATCH_MIN_DIRECTION_SCORE",
    "BRIDGE_BATCH_MIN_VOL_SCORE",
    # Contracts
    "BatchError",
    "BatchRequest",
    "BatchResponse",
    "SwingBatchRow",
    "SwingMarketParams",
    "VolBatchRow",
    # Dispatcher
    "dispatch_by_source",
    # Boundary engine
    "compute_micro_boundary",
    "load_boundary_rules",
]
