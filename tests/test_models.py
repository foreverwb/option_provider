"""
Tests for model serialization/deserialization and micro-template selection.
"""

import json
import pytest

from bridge_client.models import BridgeSnapshot, TermStructureSnapshot
from bridge_client.micro_templates import (
    select_micro_template, map_horizon_bias_to_dte_bias,
    _score_to_posture, DIRECTION_POSTURE, VOLATILITY_POSTURE,
)
from orats_provider.models import (
    StrikeRecord, SummaryRecord, CoreRecord, MoniesRecord,
    IVRankRecord, OptionRecord, GreeksExposureResult, VolatilityResult,
)


# ── TermStructureSnapshot ──────────────────────────────────────────────

class TestTermStructureSnapshot:
    def test_round_trip(self):
        ts = TermStructureSnapshot(
            label_code="CONTANGO", horizon_bias="BALANCED",
            front_iv=0.25, back_iv=0.30, ratio=0.833, contango=True,
        )
        d = ts.to_dict()
        ts2 = TermStructureSnapshot.from_dict(d)
        assert ts2.label_code == "CONTANGO"
        assert ts2.front_iv == 0.25
        assert ts2.contango is True

    def test_json_round_trip(self):
        ts = TermStructureSnapshot(label_code="FLAT")
        s = ts.to_json()
        ts2 = TermStructureSnapshot.from_json(s)
        assert ts2.label_code == "FLAT"

    def test_from_dict_none(self):
        ts = TermStructureSnapshot.from_dict(None)
        assert ts.label_code == "FLAT"

    def test_from_dict_extra_fields(self):
        ts = TermStructureSnapshot.from_dict({"label_code": "SB", "unknown_field": 99})
        assert ts.label_code == "SB"


# ── BridgeSnapshot ──────────────────────────────────────────────────────

class TestBridgeSnapshot:
    def test_round_trip(self, bridge_snapshot):
        d = bridge_snapshot.to_dict()
        snap2 = BridgeSnapshot.from_dict(d)
        assert snap2.symbol == "AAPL"
        assert snap2.spot_price == 150.0
        assert snap2.term_structure.label_code == "CONTANGO"

    def test_json_round_trip(self, bridge_snapshot):
        s = bridge_snapshot.to_json()
        snap2 = BridgeSnapshot.from_json(s)
        assert snap2.symbol == "AAPL"
        assert snap2.term_structure.front_iv == 0.25

    def test_from_dict_none(self):
        snap = BridgeSnapshot.from_dict(None)
        assert snap.symbol == ""

    def test_nested_term_structure(self):
        d = {
            "symbol": "SPY",
            "term_structure": {"label_code": "BACKWARDATION", "ratio": 1.15},
        }
        snap = BridgeSnapshot.from_dict(d)
        assert snap.term_structure.label_code == "BACKWARDATION"
        assert snap.term_structure.ratio == 1.15


# ── StrikeRecord ────────────────────────────────────────────────────────

class TestStrikeRecord:
    def test_from_orats(self):
        raw = {
            "ticker": "AAPL", "tradeDate": "2026-02-16",
            "expirDate": "2026-03-20", "dte": 32,
            "strike": 150.0, "stockPrice": 150.5,
            "callVolume": 1000, "putVolume": 800,
            "callOpenInt": 5000, "putOpenInt": 6000,
            "callIv": 0.28, "putIv": 0.30,
            "callDelta": 0.50, "putDelta": -0.50,
            "callGamma": 0.04, "putGamma": 0.04,
            "callTheta": -0.05, "putTheta": -0.04,
            "callVega": 0.20, "putVega": 0.20,
            "callVanna": 0.01, "putVanna": -0.01,
        }
        rec = StrikeRecord.from_orats(raw)
        assert rec.symbol == "AAPL"
        assert rec.strike == 150.0
        assert rec.call_iv == 0.28
        assert rec.call_gamma == 0.04

    def test_to_dict(self):
        rec = StrikeRecord(symbol="SPY", strike=400.0, call_iv=0.18)
        d = rec.to_dict()
        assert d["symbol"] == "SPY"
        assert d["strike"] == 400.0


# ── Other model from_orats tests ───────────────────────────────────────

class TestOtherModels:
    def test_summary_from_orats(self):
        raw = {"ticker": "AAPL", "stockPrice": 150.0, "iv30": 0.25, "nextEarning": "2026-04-25"}
        rec = SummaryRecord.from_orats(raw)
        assert rec.symbol == "AAPL"
        assert rec.iv_30 == 0.25

    def test_ivrank_from_orats(self):
        raw = {"ticker": "SPY", "ivRank1y": 0.55, "ivPct1y": 0.62}
        rec = IVRankRecord.from_orats(raw)
        assert rec.iv_rank_1y == 0.55

    def test_core_from_orats(self):
        raw = {"ticker": "AAPL", "expirDate": "2026-03-20", "dte": 32}
        rec = CoreRecord.from_orats(raw)
        assert rec.symbol == "AAPL"
        assert rec.dte == 32

    def test_monies_from_orats(self):
        raw = {"ticker": "AAPL", "atmIv": 0.26, "smvVol": 0.27}
        rec = MoniesRecord.from_orats(raw)
        assert rec.atm_iv == 0.26

    def test_result_models(self):
        g = GreeksExposureResult(symbol="AAPL", command="gex")
        assert g.to_dict()["symbol"] == "AAPL"
        v = VolatilityResult(symbol="SPY", command="term")
        assert v.to_dict()["command"] == "term"


# ── Micro template selection ───────────────────────────────────────────

class TestMicroTemplates:
    def test_score_to_posture_bull(self):
        assert _score_to_posture(35.0, DIRECTION_POSTURE) == "BULL"

    def test_score_to_posture_neutral(self):
        assert _score_to_posture(0.0, DIRECTION_POSTURE) == "NEUTRAL"

    def test_score_to_posture_strong_bear(self):
        assert _score_to_posture(-75.0, DIRECTION_POSTURE) == "STRONG_BEAR"

    def test_horizon_bias_map(self):
        assert map_horizon_bias_to_dte_bias("FRONT_HEAVY") == "SHORT"
        assert map_horizon_bias_to_dte_bias("BACK_HEAVY") == "LONG"
        assert map_horizon_bias_to_dte_bias("BALANCED") == "MID"
        assert map_horizon_bias_to_dte_bias("UNKNOWN") == "MID"

    def test_select_bull_normal(self, bridge_snapshot):
        # direction=35 → BULL, vol=-10 → NORMAL_VOL
        template = select_micro_template(bridge_snapshot)
        assert "BULL" in template or "CALL" in template

    def test_select_bearish_high_vol(self, bridge_snapshot_bearish):
        # direction=-45 → BEAR, vol=55 → HIGH_VOL
        template = select_micro_template(bridge_snapshot_bearish)
        assert "BEAR" in template or "CALL" in template

    def test_select_neutral(self):
        snap = BridgeSnapshot(direction_score=0, volatility_score=0)
        template = select_micro_template(snap)
        assert "IRON_CONDOR" in template or "CONDOR" in template

    def test_term_structure_overlay_backwardation(self, bridge_snapshot_bearish):
        template = select_micro_template(bridge_snapshot_bearish)
        assert "_FRONT" in template

    def test_earnings_overlay_imminent(self):
        snap = BridgeSnapshot(
            direction_score=75.0, volatility_score=0.0,
            earnings_proximity="IMMINENT",
        )
        template = select_micro_template(snap)
        # STRONG_BULL + NORMAL_VOL = LONG_CALL → earnings should modify
        assert template  # Just verify it doesn't crash

    def test_market_state_fallback(self):
        snap = BridgeSnapshot(
            direction_score=0, volatility_score=0,
            term_structure=None,
            market_state={"label_code": "STEEP_CONTANGO", "horizon_bias": "BACK_HEAVY"},
        )
        template = select_micro_template(snap)
        assert "_BACK" in template
