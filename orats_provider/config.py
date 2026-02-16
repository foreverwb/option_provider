"""
ORATS API configuration — token management, default parameters, field mappings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional

# ── API base URL ────────────────────────────────────────────────────────

ORATS_BASE_URL = "https://api.orats.io/datav2"

# ── Rate limiting ───────────────────────────────────────────────────────

DEFAULT_RATE_LIMIT = 120          # requests per window
DEFAULT_RATE_WINDOW_SEC = 60.0    # sliding window length

# ── Cache defaults ──────────────────────────────────────────────────────

DEFAULT_CACHE_TTL = 300           # seconds

# ── Default parameters ──────────────────────────────────────────────────

DEFAULT_DTE_MIN = 7
DEFAULT_DTE_MAX = 90
DEFAULT_MONEYNESS_RANGE = 0.20    # ±20% from ATM

# ── Field mappings (ORATS JSON → internal model names) ──────────────────

STRIKES_FIELD_MAP: Dict[str, str] = {
    "ticker": "symbol",
    "tradeDate": "trade_date",
    "expirDate": "expiry_date",
    "dte": "dte",
    "strike": "strike",
    "stockPrice": "spot_price",
    "callVolume": "call_volume",
    "putVolume": "put_volume",
    "callOpenInt": "call_oi",
    "putOpenInt": "put_oi",
    "callIv": "call_iv",
    "putIv": "put_iv",
    "callDelta": "call_delta",
    "putDelta": "put_delta",
    "callGamma": "call_gamma",
    "putGamma": "put_gamma",
    "callTheta": "call_theta",
    "putTheta": "put_theta",
    "callVega": "call_vega",
    "putVega": "put_vega",
    "callBidPrice": "call_bid",
    "callAskPrice": "call_ask",
    "putBidPrice": "put_bid",
    "putAskPrice": "put_ask",
    "callMidPrice": "call_mid",
    "putMidPrice": "put_mid",
    "callSmvVol": "call_smv_vol",
    "putSmvVol": "put_smv_vol",
    "residualRate": "residual_rate",
    "callVanna": "call_vanna",
    "putVanna": "put_vanna",
}

SUMMARY_FIELD_MAP: Dict[str, str] = {
    "ticker": "symbol",
    "tradeDate": "trade_date",
    "stockPrice": "spot_price",
    "annActDiv": "annual_dividend",
    "annIdiv": "implied_dividend",
    "borrow30": "borrow_30",
    "borrow2y": "borrow_2y",
    "ivMean30": "iv_mean_30",
    "ivMean60": "iv_mean_60",
    "ivMean90": "iv_mean_90",
    "iv30": "iv_30",
    "iv60": "iv_60",
    "iv90": "iv_90",
    "ivPct1m": "iv_pct_1m",
    "ivPct1y": "iv_pct_1y",
    "ivRank1m": "iv_rank_1m",
    "ivRank1y": "iv_rank_1y",
    "slope": "skew_slope",
    "deriv": "skew_deriv",
    "nextEarning": "next_earning",
    "confidence": "confidence",
}

IVRANK_FIELD_MAP: Dict[str, str] = {
    "ticker": "symbol",
    "tradeDate": "trade_date",
    "ivRank1m": "iv_rank_1m",
    "ivRank3m": "iv_rank_3m",
    "ivRank6m": "iv_rank_6m",
    "ivRank1y": "iv_rank_1y",
    "ivPct1m": "iv_pct_1m",
    "ivPct3m": "iv_pct_3m",
    "ivPct6m": "iv_pct_6m",
    "ivPct1y": "iv_pct_1y",
    "iv30": "iv_30",
    "iv60": "iv_60",
    "iv90": "iv_90",
}


@dataclass
class OratsConfig:
    """Runtime configuration for ORATS API access."""

    token: str = ""
    base_url: str = ORATS_BASE_URL
    rate_limit: int = DEFAULT_RATE_LIMIT
    rate_window_sec: float = DEFAULT_RATE_WINDOW_SEC
    cache_ttl: int = DEFAULT_CACHE_TTL
    dte_min: int = DEFAULT_DTE_MIN
    dte_max: int = DEFAULT_DTE_MAX
    moneyness_range: float = DEFAULT_MONEYNESS_RANGE

    def __post_init__(self) -> None:
        if not self.token:
            self.token = os.environ.get("ORATS_TOKEN", "")

    @classmethod
    def from_env(cls) -> "OratsConfig":
        return cls(
            token=os.environ.get("ORATS_TOKEN", ""),
            base_url=os.environ.get("ORATS_BASE_URL", ORATS_BASE_URL),
        )
