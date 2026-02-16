"""
Decoupled data models for Bridge snapshots.
Mirrors volatility_analysis/bridge/spec.py field-for-field.
Zero dependency on core modules — safe to use in external services.
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

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------
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
class BridgeSnapshot:
    """
    Complete bridge snapshot for a single symbol.
    Mirrors all fields from volatility_analysis/bridge/spec.py.
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

    # --- Market state (flat fields for backward compat) ---
    market_state: Dict[str, Any] = field(default_factory=dict)

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
            else:
                filtered[k] = v
        return cls(**filtered)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, raw: str) -> "BridgeSnapshot":
        return cls.from_dict(json.loads(raw))
