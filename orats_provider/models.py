from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ExpirationFilter(Enum):
    WEEKLY = "w"
    MONTHLY = "m"
    QUARTERLY = "q"
    FRONT_DATED = "fd"
    ALL = "*"


class ContractFilter(Enum):
    CALLS = "calls"
    PUTS = "puts"
    ITM = "itm"
    ATM = "atm"
    NTM = "ntm"


class VolMetric(Enum):
    IV = "iv"
    IV_MID = "ivmid"
    IV_ASK = "ivask"
    DELTA = "delta"
    GAMMA = "gamma"
    VEGA = "vega"
    RHO = "rho"
    VOLATILITY_MID = "smvVol"


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


@dataclass
class StrikeRow:
    ticker: str
    trade_date: str
    expir_date: str
    dte: int
    strike: float
    stock_price: float
    call_volume: int = 0
    call_open_interest: int = 0
    put_volume: int = 0
    put_open_interest: int = 0
    call_bid_price: float = 0.0
    call_value: float = 0.0
    call_ask_price: float = 0.0
    put_bid_price: float = 0.0
    put_value: float = 0.0
    put_ask_price: float = 0.0
    call_bid_iv: float = 0.0
    call_mid_iv: float = 0.0
    call_ask_iv: float = 0.0
    put_bid_iv: float = 0.0
    put_mid_iv: float = 0.0
    put_ask_iv: float = 0.0
    smv_vol: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    phi: float = 0.0
    ext_smv_vol: float = 0.0
    spot_price: float = 0.0

    @classmethod
    def from_orats(cls, row: Dict[str, Any]) -> "StrikeRow":
        return cls(
            ticker=str(row.get("ticker", "") or ""),
            trade_date=str(row.get("tradeDate", "") or ""),
            expir_date=str(row.get("expirDate", "") or ""),
            dte=_to_int(row.get("dte", 0)),
            strike=_to_float(row.get("strike", 0.0)),
            stock_price=_to_float(row.get("stockPrice", 0.0)),
            call_volume=_to_int(row.get("callVolume", 0)),
            call_open_interest=_to_int(row.get("callOpenInterest", 0)),
            put_volume=_to_int(row.get("putVolume", 0)),
            put_open_interest=_to_int(row.get("putOpenInterest", 0)),
            call_bid_price=_to_float(row.get("callBidPrice", 0.0)),
            call_value=_to_float(row.get("callValue", 0.0)),
            call_ask_price=_to_float(row.get("callAskPrice", 0.0)),
            put_bid_price=_to_float(row.get("putBidPrice", 0.0)),
            put_value=_to_float(row.get("putValue", 0.0)),
            put_ask_price=_to_float(row.get("putAskPrice", 0.0)),
            call_bid_iv=_to_float(row.get("callBidIv", 0.0)),
            call_mid_iv=_to_float(row.get("callMidIv", 0.0)),
            call_ask_iv=_to_float(row.get("callAskIv", 0.0)),
            put_bid_iv=_to_float(row.get("putBidIv", 0.0)),
            put_mid_iv=_to_float(row.get("putMidIv", 0.0)),
            put_ask_iv=_to_float(row.get("putAskIv", 0.0)),
            smv_vol=_to_float(row.get("smvVol", 0.0)),
            delta=_to_float(row.get("delta", 0.0)),
            gamma=_to_float(row.get("gamma", 0.0)),
            theta=_to_float(row.get("theta", 0.0)),
            vega=_to_float(row.get("vega", 0.0)),
            rho=_to_float(row.get("rho", 0.0)),
            phi=_to_float(row.get("phi", 0.0)),
            ext_smv_vol=_to_float(row.get("extSmvVol", 0.0)),
            spot_price=_to_float(row.get("spotPrice", row.get("stockPrice", 0.0))),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "tradeDate": self.trade_date,
            "expirDate": self.expir_date,
            "dte": self.dte,
            "strike": self.strike,
            "stockPrice": self.stock_price,
            "callVolume": self.call_volume,
            "callOpenInterest": self.call_open_interest,
            "putVolume": self.put_volume,
            "putOpenInterest": self.put_open_interest,
            "callMidIv": self.call_mid_iv,
            "putMidIv": self.put_mid_iv,
            "smvVol": self.smv_vol,
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
            "spotPrice": self.spot_price,
        }


@dataclass
class ExposureResult:
    symbol: str
    as_of: str
    metric_name: str
    total_exposure: float
    net_exposure: float
    by_strike: List[Dict[str, Any]] = field(default_factory=list)
    by_expiry: List[Dict[str, Any]] = field(default_factory=list)
    gamma_flip_strike: Optional[float] = None
    spot_price: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "as_of": self.as_of,
            "metric_name": self.metric_name,
            "total_exposure": self.total_exposure,
            "net_exposure": self.net_exposure,
            "by_strike": self.by_strike,
            "by_expiry": self.by_expiry,
            "gamma_flip_strike": self.gamma_flip_strike,
            "spot_price": self.spot_price,
            "parameters": self.parameters,
        }


@dataclass
class VolatilityResult:
    symbol: str
    as_of: str
    metric_name: str
    data: Dict[str, Any] = field(default_factory=dict)
    spot_price: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "as_of": self.as_of,
            "metric_name": self.metric_name,
            "data": self.data,
            "spot_price": self.spot_price,
            "parameters": self.parameters,
        }
