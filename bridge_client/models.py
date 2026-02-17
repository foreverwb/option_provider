"""
Decoupled data models for Bridge snapshots.
Mirrors volatility_analysis/bridge/spec.py field-for-field.
Zero dependency on core modules — safe to use in external services.

v2.0: Added ExecutionState with confidence / liquidity / oi fields.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


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
