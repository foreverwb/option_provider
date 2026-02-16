"""
ORATS data models — all carry a from_orats() factory for JSON deserialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from .config import STRIKES_FIELD_MAP, SUMMARY_FIELD_MAP, IVRANK_FIELD_MAP


def _map_fields(raw: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    """Map ORATS JSON keys to internal field names."""
    out: Dict[str, Any] = {}
    for orats_key, internal_key in mapping.items():
        if orats_key in raw:
            out[internal_key] = raw[orats_key]
    return out


# ── Strike record ───────────────────────────────────────────────────────

@dataclass
class StrikeRecord:
    """Single strike-level record from ORATS /strikes endpoint."""

    symbol: str = ""
    trade_date: str = ""
    expiry_date: str = ""
    dte: int = 0
    strike: float = 0.0
    spot_price: float = 0.0
    call_volume: int = 0
    put_volume: int = 0
    call_oi: int = 0
    put_oi: int = 0
    call_iv: float = 0.0
    put_iv: float = 0.0
    call_delta: float = 0.0
    put_delta: float = 0.0
    call_gamma: float = 0.0
    put_gamma: float = 0.0
    call_theta: float = 0.0
    put_theta: float = 0.0
    call_vega: float = 0.0
    put_vega: float = 0.0
    call_bid: float = 0.0
    call_ask: float = 0.0
    put_bid: float = 0.0
    put_ask: float = 0.0
    call_mid: float = 0.0
    put_mid: float = 0.0
    call_smv_vol: float = 0.0
    put_smv_vol: float = 0.0
    residual_rate: float = 0.0
    call_vanna: float = 0.0
    put_vanna: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_orats(cls, raw: Dict[str, Any]) -> "StrikeRecord":
        mapped = _map_fields(raw, STRIKES_FIELD_MAP)
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in mapped.items() if k in known})


# ── Summary record ──────────────────────────────────────────────────────

@dataclass
class SummaryRecord:
    """Summary-level record from ORATS /summaries endpoint."""

    symbol: str = ""
    trade_date: str = ""
    spot_price: float = 0.0
    annual_dividend: float = 0.0
    implied_dividend: float = 0.0
    borrow_30: float = 0.0
    borrow_2y: float = 0.0
    iv_mean_30: float = 0.0
    iv_mean_60: float = 0.0
    iv_mean_90: float = 0.0
    iv_30: float = 0.0
    iv_60: float = 0.0
    iv_90: float = 0.0
    iv_pct_1m: float = 0.0
    iv_pct_1y: float = 0.0
    iv_rank_1m: float = 0.0
    iv_rank_1y: float = 0.0
    skew_slope: float = 0.0
    skew_deriv: float = 0.0
    next_earning: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_orats(cls, raw: Dict[str, Any]) -> "SummaryRecord":
        mapped = _map_fields(raw, SUMMARY_FIELD_MAP)
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in mapped.items() if k in known})


# ── Core (monies/implied) record ────────────────────────────────────────

@dataclass
class CoreRecord:
    """Record from ORATS /cores endpoint."""

    symbol: str = ""
    trade_date: str = ""
    expiry_date: str = ""
    dte: int = 0
    spot_price: float = 0.0
    strike_pct: float = 0.0
    call_iv: float = 0.0
    put_iv: float = 0.0
    atm_iv: float = 0.0
    slope: float = 0.0
    deriv: float = 0.0
    forecast_iv: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_orats(cls, raw: Dict[str, Any]) -> "CoreRecord":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        mapped: Dict[str, Any] = {}
        remap = {
            "ticker": "symbol", "tradeDate": "trade_date",
            "expirDate": "expiry_date", "stockPrice": "spot_price",
        }
        for k, v in raw.items():
            key = remap.get(k, k)
            if key in known:
                mapped[key] = v
        return cls(**mapped)


# ── IV Rank record ──────────────────────────────────────────────────────

@dataclass
class IVRankRecord:
    """IV Rank / IV Percentile from ORATS /ivrank endpoint."""

    symbol: str = ""
    trade_date: str = ""
    iv_rank_1m: float = 0.0
    iv_rank_3m: float = 0.0
    iv_rank_6m: float = 0.0
    iv_rank_1y: float = 0.0
    iv_pct_1m: float = 0.0
    iv_pct_3m: float = 0.0
    iv_pct_6m: float = 0.0
    iv_pct_1y: float = 0.0
    iv_30: float = 0.0
    iv_60: float = 0.0
    iv_90: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_orats(cls, raw: Dict[str, Any]) -> "IVRankRecord":
        mapped = _map_fields(raw, IVRANK_FIELD_MAP)
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in mapped.items() if k in known})


# ── Monies/Implied record ──────────────────────────────────────────────

@dataclass
class MoniesRecord:
    """Record from ORATS /monies/implied endpoint."""

    symbol: str = ""
    trade_date: str = ""
    expiry_date: str = ""
    dte: int = 0
    spot_price: float = 0.0
    atm_iv: float = 0.0
    smv_vol: float = 0.0
    call_smv_vol: float = 0.0
    put_smv_vol: float = 0.0
    slope: float = 0.0
    deriv: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_orats(cls, raw: Dict[str, Any]) -> "MoniesRecord":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        remap = {
            "ticker": "symbol", "tradeDate": "trade_date",
            "expirDate": "expiry_date", "stockPrice": "spot_price",
            "atmIv": "atm_iv", "smvVol": "smv_vol",
            "callSmvVol": "call_smv_vol", "putSmvVol": "put_smv_vol",
        }
        mapped: Dict[str, Any] = {}
        for k, v in raw.items():
            key = remap.get(k, k)
            if key in known:
                mapped[key] = v
        return cls(**mapped)


# ── Option chain record ────────────────────────────────────────────────

@dataclass
class OptionRecord:
    """Single option from ORATS /strikes/options endpoint."""

    symbol: str = ""
    trade_date: str = ""
    expiry_date: str = ""
    dte: int = 0
    strike: float = 0.0
    spot_price: float = 0.0
    option_type: str = ""       # "call" or "put"
    bid: float = 0.0
    ask: float = 0.0
    mid: float = 0.0
    volume: int = 0
    open_interest: int = 0
    iv: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    vanna: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_orats(cls, raw: Dict[str, Any], option_type: str = "call") -> "OptionRecord":
        prefix = "call" if option_type == "call" else "put"
        mapped = _map_fields(raw, STRIKES_FIELD_MAP)
        mapped["option_type"] = option_type
        mapped["bid"] = mapped.get(f"{prefix}_bid", 0.0)
        mapped["ask"] = mapped.get(f"{prefix}_ask", 0.0)
        mapped["mid"] = mapped.get(f"{prefix}_mid", 0.0)
        mapped["volume"] = mapped.get(f"{prefix}_volume", 0)
        mapped["open_interest"] = mapped.get(f"{prefix}_oi", 0)
        mapped["iv"] = mapped.get(f"{prefix}_iv", 0.0)
        mapped["delta"] = mapped.get(f"{prefix}_delta", 0.0)
        mapped["gamma"] = mapped.get(f"{prefix}_gamma", 0.0)
        mapped["theta"] = mapped.get(f"{prefix}_theta", 0.0)
        mapped["vega"] = mapped.get(f"{prefix}_vega", 0.0)
        mapped["vanna"] = mapped.get(f"{prefix}_vanna", 0.0)
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in mapped.items() if k in known})


# ── Result containers ───────────────────────────────────────────────────

@dataclass
class GreeksExposureResult:
    """Container for Greeks exposure calculation results."""

    symbol: str = ""
    command: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    chart_data: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VolatilityResult:
    """Container for volatility analysis results."""

    symbol: str = ""
    command: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    chart_data: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
