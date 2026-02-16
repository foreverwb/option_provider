from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TermStructureSnapshot:
    ratios: Dict[str, float] = field(default_factory=dict)
    label: Optional[str] = None
    label_code: Optional[str] = None
    ratio_30_90: Optional[float] = None
    adjustment: float = 0.0
    horizon_bias: str = "neutral"
    state_flags: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ratios": dict(self.ratios),
            "label": self.label,
            "label_code": self.label_code,
            "ratio_30_90": self.ratio_30_90,
            "adjustment": self.adjustment,
            "horizon_bias": self.horizon_bias,
            "state_flags": dict(self.state_flags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TermStructureSnapshot":
        data = data or {}
        ratios_raw = data.get("ratios")
        ratios: Dict[str, float] = {}
        if isinstance(ratios_raw, dict):
            for key, value in ratios_raw.items():
                try:
                    ratios[str(key)] = float(value)
                except (TypeError, ValueError):
                    continue

        state_flags_raw = data.get("state_flags")
        state_flags: Dict[str, bool] = {}
        if isinstance(state_flags_raw, dict):
            state_flags = {str(k): bool(v) for k, v in state_flags_raw.items()}

        ratio_30_90 = data.get("ratio_30_90")
        try:
            ratio_30_90 = float(ratio_30_90) if ratio_30_90 is not None else None
        except (TypeError, ValueError):
            ratio_30_90 = None

        adjustment = data.get("adjustment", 0.0)
        try:
            adjustment = float(adjustment)
        except (TypeError, ValueError):
            adjustment = 0.0

        hb = str(data.get("horizon_bias") or "neutral").lower()
        if hb not in {"short", "mid", "long", "neutral"}:
            hb = "neutral"

        return cls(
            ratios=ratios,
            label=data.get("label"),
            label_code=data.get("label_code"),
            ratio_30_90=ratio_30_90,
            adjustment=adjustment,
            horizon_bias=hb,
            state_flags=state_flags,
        )


@dataclass
class BridgeSnapshot:
    symbol: Optional[str] = None
    as_of: Optional[str] = None
    market_state: Dict[str, Any] = field(default_factory=dict)
    event_state: Dict[str, Any] = field(default_factory=dict)
    execution_state: Dict[str, Any] = field(default_factory=dict)
    term_structure: Optional[TermStructureSnapshot] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "as_of": self.as_of,
            "market_state": dict(self.market_state),
            "event_state": dict(self.event_state),
            "execution_state": dict(self.execution_state),
            "term_structure": self.term_structure.to_dict() if self.term_structure else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BridgeSnapshot":
        data = data or {}
        term_raw = data.get("term_structure")
        term = TermStructureSnapshot.from_dict(term_raw) if isinstance(term_raw, dict) else None
        market_state = data.get("market_state") if isinstance(data.get("market_state"), dict) else {}
        event_state = data.get("event_state") if isinstance(data.get("event_state"), dict) else {}
        execution_state = (
            data.get("execution_state") if isinstance(data.get("execution_state"), dict) else {}
        )

        return cls(
            symbol=data.get("symbol"),
            as_of=data.get("as_of"),
            market_state=market_state,
            event_state=event_state,
            execution_state=execution_state,
            term_structure=term,
        )
