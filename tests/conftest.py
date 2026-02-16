"""
Shared pytest fixtures — synthetic option chain data for testing.
"""

from __future__ import annotations

import math
import pytest
from typing import List

from bridge_client.models import BridgeSnapshot, TermStructureSnapshot
from orats_provider.models import StrikeRecord, SummaryRecord, MoniesRecord


# ── Synthetic strike chain generator ────────────────────────────────────

def make_strike_chain(
    symbol: str = "AAPL",
    spot: float = 150.0,
    num_strikes: int = 21,
    expiry_dates: List[str] | None = None,
) -> List[StrikeRecord]:
    """
    Generate a realistic synthetic option chain for testing.
    """
    if expiry_dates is None:
        expiry_dates = ["2026-03-20", "2026-04-17", "2026-06-19"]

    records = []
    strike_step = spot * 0.01  # 1% spacing
    base_strike = spot - (num_strikes // 2) * strike_step

    for i_exp, exp in enumerate(expiry_dates):
        dte = (i_exp + 1) * 30
        for i in range(num_strikes):
            strike = round(base_strike + i * strike_step, 2)
            moneyness = (strike - spot) / spot
            # Synthetic IV with skew
            base_iv = 0.25 + 0.08 * (i_exp / 3)  # Contango shape
            skew = max(0, -moneyness * 0.15)
            call_iv = max(0.05, base_iv + skew * 0.5)
            put_iv = max(0.05, base_iv + skew)

            # Synthetic greeks
            d1 = moneyness / (call_iv * math.sqrt(dte / 365)) if call_iv > 0 and dte > 0 else 0
            call_delta = max(0.01, min(0.99, 0.5 + 0.4 * math.tanh(d1)))
            put_delta = call_delta - 1.0
            gamma = max(0.0001, 0.05 * math.exp(-moneyness ** 2 / 0.02))
            vega = max(0.001, 0.3 * math.exp(-moneyness ** 2 / 0.04))
            vanna = -moneyness * gamma * 10
            theta = -0.05 * call_iv * spot / math.sqrt(max(dte, 1))

            # Synthetic OI (higher near ATM)
            atm_weight = math.exp(-moneyness ** 2 / 0.01)
            call_oi = int(1000 + 5000 * atm_weight)
            put_oi = int(800 + 6000 * atm_weight)

            records.append(StrikeRecord(
                symbol=symbol,
                trade_date="2026-02-16",
                expiry_date=exp,
                dte=dte,
                strike=strike,
                spot_price=spot,
                call_volume=int(100 + 500 * atm_weight),
                put_volume=int(80 + 400 * atm_weight),
                call_oi=call_oi,
                put_oi=put_oi,
                call_iv=round(call_iv, 4),
                put_iv=round(put_iv, 4),
                call_delta=round(call_delta, 4),
                put_delta=round(put_delta, 4),
                call_gamma=round(gamma, 6),
                put_gamma=round(gamma, 6),
                call_theta=round(theta, 4),
                put_theta=round(theta * 0.9, 4),
                call_vega=round(vega, 4),
                put_vega=round(vega, 4),
                call_smv_vol=round(call_iv * 1.02, 4),
                put_smv_vol=round(put_iv * 0.98, 4),
                residual_rate=0.0,
                call_vanna=round(vanna, 6),
                put_vanna=round(-vanna * 0.8, 6),
            ))
    return records


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def strike_chain() -> List[StrikeRecord]:
    return make_strike_chain()


@pytest.fixture
def aapl_chain() -> List[StrikeRecord]:
    return make_strike_chain("AAPL", spot=150.0)


@pytest.fixture
def bridge_snapshot() -> BridgeSnapshot:
    return BridgeSnapshot(
        symbol="AAPL",
        timestamp="2026-02-16T12:00:00Z",
        spot_price=150.0,
        prev_close=148.5,
        change_pct=1.01,
        iv_current=0.28,
        iv_percentile=65.0,
        iv_rank=58.0,
        hv_20=0.22,
        hv_60=0.20,
        iv_hv_spread=0.06,
        direction_score=35.0,
        direction_label="BULL",
        volatility_score=-10.0,
        volatility_label="NORMAL",
        composite_score=12.5,
        term_structure=TermStructureSnapshot(
            label_code="CONTANGO",
            horizon_bias="BALANCED",
            front_iv=0.25,
            back_iv=0.30,
            ratio=0.833,
            adjustment=0.02,
            contango=True,
        ),
        earnings_date="2026-04-25",
        days_to_earnings=68,
        earnings_proximity="FAR",
        recommended_strategy="BULL_CALL_SPREAD",
        strategy_confidence=0.72,
        source="bridge_api",
    )


@pytest.fixture
def bridge_snapshot_bearish() -> BridgeSnapshot:
    return BridgeSnapshot(
        symbol="TSLA",
        direction_score=-45.0,
        volatility_score=55.0,
        term_structure=TermStructureSnapshot(
            label_code="BACKWARDATION",
            horizon_bias="FRONT_HEAVY",
        ),
        earnings_proximity="IMMINENT",
    )
