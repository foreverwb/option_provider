"""
Decoupled data models for Bridge snapshots.
Mirrors volatility_analysis/bridge/spec.py field-for-field.
Zero dependency on core modules — safe to use in external services.

v2.0: Added ExecutionState with confidence / liquidity / oi fields.
v3.0: Added MicroBoundary dataclass family for centralized boundary decisions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict, fields as dc_fields
from typing import Any, Dict, List, Optional


# ======================================================================
# Helper — shared by all dataclasses in this module
# ======================================================================

def _safe_from_dict(cls, data: Dict[str, Any]):
    """Construct *cls* from *data*, silently dropping unknown keys."""
    if data is None:
        return cls()
    known = {f.name for f in dc_fields(cls)}
    filtered = {k: v for k, v in data.items() if k in known}
    return cls(**filtered)


# ======================================================================
# Existing models (v2.0)
# ======================================================================

@dataclass
class TermStructureSnapshot:
    """Term-structure profile snapshot (mirrors bridge/spec.py)."""

    label_code: str = "FLAT"
    horizon_bias: str = "NEUTRAL"
    front_iv: float = 0.0
    back_iv: float = 0.0
    ratio: float = 1.0
    adjustment: float = 0.0
    contango: bool = True
    raw_ratios: Dict[str, float] = field(default_factory=dict)

    # Extended fields from VA bridge spec
    label: Optional[str] = None
    ratio_30_90: Optional[float] = None
    state_flags: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TermStructureSnapshot":
        if data is None:
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, raw: str) -> "TermStructureSnapshot":
        return cls.from_dict(json.loads(raw))


@dataclass
class ExecutionState:
    """
    Execution-state block from bridge snapshot.
    Contains confidence, liquidity, OI availability, and posture fields
    consumed by downstream workflows (swing / vol_quant).
    """

    quadrant: Optional[str] = None
    direction_score: Optional[float] = None
    vol_score: Optional[float] = None
    direction_bias: Optional[str] = None
    vol_bias: Optional[str] = None

    # Key fields consumed by vol_quant_workflow & swing_workflow
    confidence: Optional[float] = None
    confidence_notes: Optional[str] = None
    liquidity: Optional[str] = None
    active_open_ratio: Optional[float] = None
    oi_data_available: Optional[bool] = None

    # Data quality
    data_quality: Optional[str] = None
    data_quality_issues: Optional[str] = None

    # Flow / permission
    penalized_extreme_move_low_vol: Optional[bool] = None
    flow_bias: Optional[float] = None
    trade_permission: Optional[str] = None
    permission_reasons: Optional[List[str]] = None
    disabled_structures: Optional[List[str]] = None
    watch_triggers: Optional[List[str]] = None
    what_to_monitor: Optional[str] = None

    # Posture fields
    posture_5d: Optional[str] = None
    posture_reasons: Optional[List[str]] = None
    posture_reason_codes: Optional[List[str]] = None
    posture_confidence: Optional[float] = None
    posture_inputs_snapshot: Optional[Dict[str, Any]] = None
    posture_overlay_notes: Optional[str] = None

    # Trend fields
    dir_slope_nd: Optional[float] = None
    dir_trend_label: Optional[str] = None
    trend_days_used: Optional[int] = None

    # Fear regime
    fear_regime: Optional[str] = None
    fear_reasons: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionState":
        if data is None:
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class EventState:
    """Event-state block (earnings, squeeze, index flags)."""

    earnings_date: Optional[str] = None
    days_to_earnings: Optional[int] = None
    is_earnings_window: bool = False
    is_index: bool = False
    is_squeeze: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventState":
        if data is None:
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


@dataclass
class BridgeSnapshot:
    """
    Complete bridge snapshot for a single symbol.
    v2.0: Added structured execution_state / event_state / market_state
    while maintaining backward-compatible flat fields.
    """

    # --- Identity ---
    symbol: str = ""
    timestamp: str = ""

    # --- Price context ---
    spot_price: float = 0.0
    prev_close: float = 0.0
    change_pct: float = 0.0

    # --- Volatility metrics ---
    iv_current: float = 0.0
    iv_percentile: float = 0.0
    iv_rank: float = 0.0
    hv_20: float = 0.0
    hv_60: float = 0.0
    iv_hv_spread: float = 0.0

    # --- Directional scoring ---
    direction_score: float = 0.0
    direction_label: str = ""
    volatility_score: float = 0.0
    volatility_label: str = ""
    composite_score: float = 0.0

    # --- Term structure ---
    term_structure: Optional[TermStructureSnapshot] = None

    # --- Structured sub-states (v2.0) ---
    market_state: Dict[str, Any] = field(default_factory=dict)
    event_state: Optional[EventState] = None
    execution_state: Optional[ExecutionState] = None

    # --- Earnings ---
    earnings_date: Optional[str] = None
    days_to_earnings: Optional[int] = None
    earnings_proximity: str = "NONE"

    # --- Strategy ---
    recommended_strategy: str = ""
    strategy_confidence: float = 0.0
    micro_template: str = ""

    # --- Source metadata ---
    source: str = ""
    as_of: Optional[str] = None
    data_quality: str = "OK"
    warnings: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BridgeSnapshot":
        if data is None:
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {}
        for k, v in data.items():
            if k not in known:
                continue
            if k == "term_structure" and isinstance(v, dict):
                filtered[k] = TermStructureSnapshot.from_dict(v)
            elif k == "execution_state" and isinstance(v, dict):
                filtered[k] = ExecutionState.from_dict(v)
            elif k == "event_state" and isinstance(v, dict):
                filtered[k] = EventState.from_dict(v)
            else:
                filtered[k] = v
        return cls(**filtered)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, raw: str) -> "BridgeSnapshot":
        return cls.from_dict(json.loads(raw))


# ======================================================================
# v3.0 — MicroBoundary dataclass family
# ======================================================================

# --- Enumeration constants ---

MESO_STATES = ("偏多-买波", "偏多-卖波", "偏空-买波", "偏空-卖波")
DEGRADATION_MODES = ("full", "partial", "fallback", "blocked")
EFFECTIVE_CONTEXTS = ("standard", "minimum", "event", "blocked")


# --- 1. DirectionalRange ---

@dataclass
class DirectionalRange:
    """Boundary on directional movement (price / delta)."""

    upper: Optional[float] = None
    lower: Optional[float] = None
    bias: Optional[str] = None
    direction_score: Optional[float] = None
    direction_bias: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DirectionalRange":
        return _safe_from_dict(cls, data)


# --- 2. VolRange ---

@dataclass
class VolRange:
    """Implied / realized vol boundary."""

    iv_current: Optional[float] = None
    iv_low: Optional[float] = None
    iv_high: Optional[float] = None
    rv_ref: Optional[float] = None
    vrp: Optional[float] = None
    vrp_regime: Optional[str] = None
    ivr: Optional[float] = None
    vol_score: Optional[float] = None
    vol_bias: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VolRange":
        return _safe_from_dict(cls, data)


# --- 3. LiquidityBoundary ---

@dataclass
class LiquidityBoundary:
    """Liquidity assessment and resulting strikes ceiling."""

    raw_label: Optional[str] = None
    score: Optional[float] = None
    tier: Optional[str] = None
    is_sufficient: Optional[bool] = None
    strikes_ceiling: Optional[int] = None
    active_open_ratio: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LiquidityBoundary":
        return _safe_from_dict(cls, data)


# --- 4. OIAvailability ---

@dataclass
class OIAvailability:
    """Open-interest data availability and concentration map."""

    available: Optional[bool] = None
    strikes_cap: Optional[int] = None
    concentration: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OIAvailability":
        return _safe_from_dict(cls, data)


# --- 5. ConfidenceBoundary ---

@dataclass
class ConfidenceBoundary:
    """Confidence gate result."""

    level: Optional[float] = None
    gate_passed: Optional[bool] = None
    gate_threshold: Optional[float] = None
    recommended_context: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfidenceBoundary":
        return _safe_from_dict(cls, data)


# --- 6. TemporalBoundary ---

@dataclass
class TemporalBoundary:
    """Time-based constraints (earnings, DTE cluster, squeeze / index)."""

    earnings_window: Optional[bool] = None
    days_to_earnings: Optional[int] = None
    earnings_date: Optional[str] = None
    dte_cluster: Optional[str] = None
    is_index: Optional[bool] = None
    is_squeeze: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemporalBoundary":
        return _safe_from_dict(cls, data)


# --- 7. TermStructureBoundary ---

@dataclass
class TermStructureBoundary:
    """Term structure regime label, adjustment, and scaling factors."""

    label_code: Optional[str] = None
    adjustment: Optional[float] = None
    horizon_bias: Dict[str, Any] = field(default_factory=dict)
    state_flags: Dict[str, bool] = field(default_factory=dict)
    scale_factors: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TermStructureBoundary":
        return _safe_from_dict(cls, data)


# --- 8. BaseBoundary ---

@dataclass
class BaseBoundary:
    """Composite of the seven sub-boundaries."""

    directional: Optional[DirectionalRange] = None
    vol_range: Optional[VolRange] = None
    liquidity: Optional[LiquidityBoundary] = None
    oi: Optional[OIAvailability] = None
    confidence: Optional[ConfidenceBoundary] = None
    temporal: Optional[TemporalBoundary] = None
    term_structure: Optional[TermStructureBoundary] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "directional": self.directional.to_dict() if self.directional else None,
            "vol_range": self.vol_range.to_dict() if self.vol_range else None,
            "liquidity": self.liquidity.to_dict() if self.liquidity else None,
            "oi": self.oi.to_dict() if self.oi else None,
            "confidence": self.confidence.to_dict() if self.confidence else None,
            "temporal": self.temporal.to_dict() if self.temporal else None,
            "term_structure": self.term_structure.to_dict() if self.term_structure else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseBoundary":
        if data is None:
            return cls()
        return cls(
            directional=DirectionalRange.from_dict(data.get("directional")) if data.get("directional") else None,
            vol_range=VolRange.from_dict(data.get("vol_range")) if data.get("vol_range") else None,
            liquidity=LiquidityBoundary.from_dict(data.get("liquidity")) if data.get("liquidity") else None,
            oi=OIAvailability.from_dict(data.get("oi")) if data.get("oi") else None,
            confidence=ConfidenceBoundary.from_dict(data.get("confidence")) if data.get("confidence") else None,
            temporal=TemporalBoundary.from_dict(data.get("temporal")) if data.get("temporal") else None,
            term_structure=TermStructureBoundary.from_dict(data.get("term_structure")) if data.get("term_structure") else None,
        )


# --- 9. SwingOverlay ---

@dataclass
class SwingOverlay:
    """Strategy overlay specific to swing_workflow."""

    scenario: Optional[str] = None
    suggested_dyn_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SwingOverlay":
        return _safe_from_dict(cls, data)


# --- 10. VolQuantOverlay ---

@dataclass
class VolQuantOverlay:
    """Strategy overlay specific to vol_quant_workflow (gexbot)."""

    gexbot_context: Optional[str] = None
    horizon_scales: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VolQuantOverlay":
        return _safe_from_dict(cls, data)


# --- 11. StrategyOverlay ---

@dataclass
class StrategyOverlay:
    """Per-workflow strategy overlays (both optional)."""

    swing: Optional[SwingOverlay] = None
    vol_quant: Optional[VolQuantOverlay] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "swing": self.swing.to_dict() if self.swing else None,
            "vol_quant": self.vol_quant.to_dict() if self.vol_quant else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyOverlay":
        if data is None:
            return cls()
        return cls(
            swing=SwingOverlay.from_dict(data.get("swing")) if data.get("swing") else None,
            vol_quant=VolQuantOverlay.from_dict(data.get("vol_quant")) if data.get("vol_quant") else None,
        )


# --- 12. Degradation ---

@dataclass
class Degradation:
    """Tracks data completeness and fallback behaviour."""

    mode: Optional[str] = None                       # full | partial | fallback | blocked
    missing_fields: List[str] = field(default_factory=list)
    fallback_rules_applied: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Degradation":
        return _safe_from_dict(cls, data)


# --- 13. BoundaryMetadata ---

@dataclass
class BoundaryMetadata:
    """Provenance / version information for the boundary payload."""

    data_completeness: Optional[float] = None        # 0.0 – 1.0
    source_freshness: Optional[str] = None           # ISO timestamp
    boundary_version: Optional[str] = None           # e.g. "1.0"
    rules_source: Optional[str] = None               # e.g. "boundary_rules.yaml"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoundaryMetadata":
        return _safe_from_dict(cls, data)


# --- 14. MicroBoundary (root) ---

@dataclass
class MicroBoundary:
    """
    Root dataclass for the centralized micro-boundary decision payload.
    Assembled by the bridge middleware and transported in
    SwingBatchRow.micro_boundary / VolBatchRow.micro_boundary.
    """

    ticker: Optional[str] = None
    timestamp: Optional[str] = None
    meso_state: Optional[str] = None                 # 偏多-买波 / 偏多-卖波 / 偏空-买波 / 偏空-卖波
    base_boundary: Optional[BaseBoundary] = None
    effective_strikes: Optional[int] = None
    effective_context: Optional[str] = None          # standard / minimum / event / blocked
    strategy_overlay: Optional[StrategyOverlay] = None
    degradation: Optional[Degradation] = None
    metadata: Optional[BoundaryMetadata] = None

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "timestamp": self.timestamp,
            "meso_state": self.meso_state,
            "base_boundary": self.base_boundary.to_dict() if self.base_boundary else None,
            "effective_strikes": self.effective_strikes,
            "effective_context": self.effective_context,
            "strategy_overlay": self.strategy_overlay.to_dict() if self.strategy_overlay else None,
            "degradation": self.degradation.to_dict() if self.degradation else None,
            "metadata": self.metadata.to_dict() if self.metadata else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MicroBoundary":
        if data is None:
            return cls()
        return cls(
            ticker=data.get("ticker"),
            timestamp=data.get("timestamp"),
            meso_state=data.get("meso_state"),
            base_boundary=BaseBoundary.from_dict(data.get("base_boundary")) if data.get("base_boundary") else None,
            effective_strikes=data.get("effective_strikes"),
            effective_context=data.get("effective_context"),
            strategy_overlay=StrategyOverlay.from_dict(data.get("strategy_overlay")) if data.get("strategy_overlay") else None,
            degradation=Degradation.from_dict(data.get("degradation")) if data.get("degradation") else None,
            metadata=BoundaryMetadata.from_dict(data.get("metadata")) if data.get("metadata") else None,
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, raw: str) -> "MicroBoundary":
        return cls.from_dict(json.loads(raw))
