"""
Tests for boundary_engine.py — Task 1.3.

Coverage matrix
---------------
4 meso states × 7+ degradation/edge scenarios
+ boundary cases (empty dict, None, all-None exec_state)
+ term_structure scale-factor alignment verification
"""

from __future__ import annotations

import json
import pytest
from typing import Any, Dict

from bridge_provider.boundary_engine import (
    _DEFAULT_RULES,
    _compute_confidence,
    _compute_directional_range,
    _compute_effective_context,
    _compute_effective_strikes,
    _compute_liquidity,
    _compute_oi,
    _compute_swing_overlay,
    _compute_temporal,
    _compute_term_structure,
    _compute_vol_quant_overlay,
    _compute_vol_range,
    _resolve_meso_state,
    compute_micro_boundary,
    load_boundary_rules,
)
from bridge_provider.models import (
    BaseBoundary,
    ConfidenceBoundary,
    LiquidityBoundary,
    MicroBoundary,
    OIAvailability,
    TemporalBoundary,
    TermStructureBoundary,
)


# ======================================================================
# Fixtures — reusable bridge_data builders
# ======================================================================

def _full_bridge(
    direction_bias: str = "偏多",
    vol_bias: str = "买波",
    confidence: float = 0.65,
    liquidity: str = "good",
    oi_available: bool = True,
    data_quality: str = "ok",
    trade_permission: str = "允许",
    days_to_earnings: int | None = None,
    is_earnings_window: bool = False,
    term_label_code: str = "FLAT",
    term_state_flags: dict | None = None,
) -> Dict[str, Any]:
    """Build a complete bridge_data dict with sensible defaults."""
    return {
        "symbol": "AAPL",
        "as_of": "2026-02-28",
        "market_state": {
            "vix": 18.5,
            "ivr": 45.0,
            "iv30": 32.0,
            "hv20": 28.0,
        },
        "event_state": {
            "earnings_date": "2026-03-15" if days_to_earnings is not None else None,
            "days_to_earnings": days_to_earnings,
            "is_earnings_window": is_earnings_window or (days_to_earnings is not None and 0 <= days_to_earnings <= 14),
            "is_index": False,
            "is_squeeze": False,
        },
        "execution_state": {
            "quadrant": f"{direction_bias}-{vol_bias}",
            "direction_score": 0.72,
            "vol_score": 0.15,
            "direction_bias": direction_bias,
            "vol_bias": vol_bias,
            "confidence": confidence,
            "confidence_notes": "test",
            "liquidity": liquidity,
            "active_open_ratio": 0.35,
            "oi_data_available": oi_available,
            "data_quality": data_quality,
            "trade_permission": trade_permission,
            "flow_bias": 0.12,
            "fear_regime": "normal",
        },
        "term_structure": {
            "label_code": term_label_code,
            "adjustment": -0.05,
            "horizon_bias": {"short": 0.20, "mid": -0.05, "long": -0.10},
            "state_flags": term_state_flags or {},
        },
    }


@pytest.fixture
def rules():
    return load_boundary_rules()


# ======================================================================
# Rules loader
# ======================================================================

class TestLoadBoundaryRules:
    def test_loads_from_yaml(self):
        r = load_boundary_rules()
        assert r["version"] == "1.0"
        assert "liquidity" in r

    def test_fallback_on_bad_path(self):
        r = load_boundary_rules("/nonexistent/path.yaml")
        assert r["version"] == "1.0"
        assert r is not _DEFAULT_RULES  # should be a copy


# ======================================================================
# _resolve_meso_state
# ======================================================================

class TestResolveMesoState:
    @pytest.mark.parametrize("d_bias,v_bias,expected", [
        ("偏多", "买波", "偏多-买波"),
        ("偏多", "卖波", "偏多-卖波"),
        ("偏空", "买波", "偏空-买波"),
        ("偏空", "卖波", "偏空-卖波"),
        (None, None, "中性-中性"),
    ])
    def test_combinations(self, d_bias, v_bias, expected):
        es = {"direction_bias": d_bias, "vol_bias": v_bias}
        assert _resolve_meso_state(es) == expected


# ======================================================================
# Full data — 4 meso states
# ======================================================================

class TestFullData:
    """Mode=full for each of the 4 canonical meso states."""

    @pytest.mark.parametrize("d_bias,v_bias", [
        ("偏多", "买波"),
        ("偏多", "卖波"),
        ("偏空", "买波"),
        ("偏空", "卖波"),
    ])
    def test_full_data_all_quadrants(self, d_bias, v_bias):
        bd = _full_bridge(
            direction_bias=d_bias,
            vol_bias=v_bias,
            confidence=0.65 if "买波" == v_bias else 0.72,
        )
        mb = compute_micro_boundary(bd)

        assert mb.meso_state == f"{d_bias}-{v_bias}"
        assert mb.degradation.mode == "full"
        assert mb.base_boundary.confidence.gate_passed is True
        assert mb.effective_strikes > 0
        assert mb.effective_context in ("standard", "event")
        assert mb.ticker == "AAPL"

        # JSON serialisable
        d = mb.to_dict()
        assert json.dumps(d)


# ======================================================================
# Degradation scenarios
# ======================================================================

class TestDegradationScenarios:

    def test_oi_unavailable_partial(self):
        """OI unavailable → mode=partial, strikes_cap=11."""
        bd = _full_bridge(oi_available=False)
        mb = compute_micro_boundary(bd)
        assert mb.degradation.mode == "partial"
        assert mb.base_boundary.oi.available is False
        assert mb.base_boundary.oi.strikes_cap == 11
        assert mb.effective_strikes <= 11

    def test_liquidity_poor_buy_vol_blocked(self):
        """Poor liquidity + 买波 → is_sufficient=False → blocked."""
        bd = _full_bridge(liquidity="poor", vol_bias="买波")
        mb = compute_micro_boundary(bd)
        assert mb.degradation.mode == "blocked"
        assert mb.base_boundary.liquidity.is_sufficient is False

    def test_liquidity_poor_sell_vol_not_blocked(self):
        """Poor liquidity + 卖波 → is_sufficient=True → not blocked for that reason."""
        bd = _full_bridge(liquidity="poor", vol_bias="卖波", confidence=0.72)
        mb = compute_micro_boundary(bd)
        # Liquidity alone doesn't block 卖波
        assert mb.base_boundary.liquidity.is_sufficient is True
        # mode could be partial (due to 0 missing fields it's actually full if
        # the confidence gate passes).
        assert mb.degradation.mode in ("full", "partial")

    def test_confidence_below_buy_vol_min(self):
        """Confidence 0.25 < buy_vol_min 0.35 → context=minimum."""
        bd = _full_bridge(confidence=0.25, vol_bias="买波")
        mb = compute_micro_boundary(bd)
        assert mb.base_boundary.confidence.gate_passed is False
        assert mb.base_boundary.confidence.recommended_context == "minimum"
        assert mb.effective_context == "minimum"

    def test_confidence_below_blocked_threshold(self):
        """Confidence 0.10 < blocked_threshold 0.20 → blocked."""
        bd = _full_bridge(confidence=0.10)
        mb = compute_micro_boundary(bd)
        assert mb.base_boundary.confidence.recommended_context == "blocked"
        assert mb.effective_context == "blocked"
        assert mb.degradation.mode == "blocked"

    def test_earnings_window_event_context(self):
        """In earnings window → context=event, dte_cluster has event."""
        bd = _full_bridge(days_to_earnings=8, is_earnings_window=True)
        mb = compute_micro_boundary(bd)
        assert mb.base_boundary.temporal.earnings_window is True
        assert mb.effective_context == "event"
        assert "event" in mb.base_boundary.temporal.dte_cluster

    def test_earnings_imminent(self):
        """days_to_earnings=2 → dte_cluster = event_imminent."""
        bd = _full_bridge(days_to_earnings=2, is_earnings_window=True)
        mb = compute_micro_boundary(bd)
        assert mb.base_boundary.temporal.dte_cluster == "event_imminent"
        assert mb.effective_context == "event"

    def test_oi_unavailable_plus_earnings(self):
        """Combined: OI unavailable + earnings window."""
        bd = _full_bridge(oi_available=False, days_to_earnings=5, is_earnings_window=True)
        mb = compute_micro_boundary(bd)
        assert mb.degradation.mode == "partial"
        assert mb.effective_context == "event"
        assert mb.base_boundary.oi.strikes_cap == 11

    def test_trade_permission_blocked(self):
        """trade_permission != '允许' → context=blocked."""
        bd = _full_bridge(trade_permission="禁止")
        mb = compute_micro_boundary(bd)
        assert mb.effective_context == "blocked"


# ======================================================================
# Boundary / edge cases
# ======================================================================

class TestEdgeCases:

    def test_empty_bridge_data(self):
        """bridge_data = {} → no exception, all fallback."""
        mb = compute_micro_boundary({})
        assert mb.ticker is None
        assert mb.degradation.mode in ("fallback", "blocked")
        assert mb.effective_strikes >= 7
        d = mb.to_dict()
        assert json.dumps(d)

    def test_none_bridge_data(self):
        """bridge_data = None → no exception."""
        mb = compute_micro_boundary(None)
        assert mb.ticker is None
        assert mb.degradation is not None

    def test_execution_state_all_none(self):
        """All exec_state fields None → all fallback, no exception."""
        bd = {
            "execution_state": {k: None for k in [
                "direction_score", "vol_score", "direction_bias", "vol_bias",
                "confidence", "liquidity", "active_open_ratio",
                "oi_data_available", "data_quality", "trade_permission",
                "fear_regime",
            ]},
            "market_state": {},
            "event_state": {},
            "term_structure": {},
        }
        mb = compute_micro_boundary(bd)
        assert mb.degradation.mode in ("fallback", "blocked")
        assert len(mb.degradation.missing_fields) > 0
        assert json.dumps(mb.to_dict())

    def test_confidence_none_fallback_default(self):
        """confidence=None → fallback to missing_default=0.50."""
        bd = _full_bridge(confidence=None)
        # Manually set confidence to None (since _full_bridge passes it)
        bd["execution_state"]["confidence"] = None
        mb = compute_micro_boundary(bd)
        # Default 0.50 should pass buy_vol_min gate (0.35)
        assert mb.base_boundary.confidence.level == 0.50
        assert "confidence_missing" in "".join(mb.degradation.fallback_rules_applied)

    def test_liquidity_none_fallback(self):
        """liquidity=None → fallback to default strikes."""
        bd = _full_bridge()
        bd["execution_state"]["liquidity"] = None
        mb = compute_micro_boundary(bd)
        assert "liquidity_label_missing" in "".join(mb.degradation.fallback_rules_applied)
        # Should use default_strikes (15) from rules
        assert mb.base_boundary.liquidity.tier == "unknown"

    def test_data_quality_poor_penalizes_confidence(self):
        """data_quality='poor' → confidence *= 0.8."""
        bd = _full_bridge(confidence=0.50, data_quality="poor")
        mb = compute_micro_boundary(bd)
        # 0.50 * 0.80 = 0.40 which is >= buy_vol_min 0.35
        assert mb.base_boundary.confidence.level == pytest.approx(0.40, abs=0.01)


# ======================================================================
# Term structure scale-factor alignment
# ======================================================================

class TestTermStructureAlignment:
    """
    Verify scale_factors match gexbot_param_resolver.py logic:
    base weights × state_override multipliers for each active flag.
    """

    def test_no_active_flags(self, rules):
        """No active flags → base weights only."""
        td = {"label_code": "FLAT", "adjustment": 0.0, "state_flags": {}}
        ts = _compute_term_structure(td, rules)
        # Base: gex=1.0, skew=0.8, vex=1.0, term=1.0
        assert ts.scale_factors["gex_scale"] == pytest.approx(1.0)
        assert ts.scale_factors["skew_scale"] == pytest.approx(0.8)
        assert ts.scale_factors["vex_scale"] == pytest.approx(1.0)
        assert ts.scale_factors["term_scale"] == pytest.approx(1.0)

    def test_short_low_active(self, rules):
        """short_low flag active → gex*0.85, skew*0.90, trigger*0.85."""
        td = {"label_code": "short_low", "adjustment": -0.05,
              "state_flags": {"short_low": True}}
        ts = _compute_term_structure(td, rules)
        assert ts.scale_factors["gex_scale"] == pytest.approx(1.0 * 0.85, abs=1e-4)
        assert ts.scale_factors["skew_scale"] == pytest.approx(0.8 * 0.90, abs=1e-4)
        assert ts.scale_factors["trigger_scale"] == pytest.approx(1.0 * 0.85, abs=1e-4)

    def test_full_inversion_active(self, rules):
        """full_inversion → gex*0.7, skew*0.8, vex*0.85, term*0.85."""
        td = {"label_code": "full_inversion", "adjustment": -0.10,
              "state_flags": {"full_inversion": True}}
        ts = _compute_term_structure(td, rules)
        assert ts.scale_factors["gex_scale"] == pytest.approx(1.0 * 0.7, abs=1e-4)
        assert ts.scale_factors["skew_scale"] == pytest.approx(0.8 * 0.8, abs=1e-4)
        assert ts.scale_factors["vex_scale"] == pytest.approx(1.0 * 0.85, abs=1e-4)
        assert ts.scale_factors["term_scale"] == pytest.approx(1.0 * 0.85, abs=1e-4)

    def test_short_inversion_active(self, rules):
        td = {"label_code": "short_inversion", "adjustment": -0.03,
              "state_flags": {"short_inversion": True}}
        ts = _compute_term_structure(td, rules)
        assert ts.scale_factors["gex_scale"] == pytest.approx(1.0 * 0.8, abs=1e-4)
        assert ts.scale_factors["skew_scale"] == pytest.approx(0.8 * 0.9, abs=1e-4)
        assert ts.scale_factors["vex_scale"] == pytest.approx(1.0 * 0.95, abs=1e-4)
        assert ts.scale_factors["term_scale"] == pytest.approx(1.0 * 0.95, abs=1e-4)

    def test_far_elevated_active(self, rules):
        td = {"label_code": "far_elevated", "adjustment": 0.05,
              "state_flags": {"far_elevated": True}}
        ts = _compute_term_structure(td, rules)
        assert ts.scale_factors["gex_scale"] == pytest.approx(1.0 * 1.0, abs=1e-4)
        assert ts.scale_factors["skew_scale"] == pytest.approx(0.8 * 1.0, abs=1e-4)
        assert ts.scale_factors["vex_scale"] == pytest.approx(1.0 * 1.15, abs=1e-4)
        assert ts.scale_factors["term_scale"] == pytest.approx(1.0 * 1.15, abs=1e-4)

    def test_multiple_flags_compound(self, rules):
        """Two flags active → multiplicative composition."""
        td = {"label_code": "complex", "adjustment": 0.0,
              "state_flags": {"short_low": True, "full_inversion": True}}
        ts = _compute_term_structure(td, rules)
        # gex: 1.0 * 0.85 (short_low) * 0.7 (full_inv) = 0.595
        assert ts.scale_factors["gex_scale"] == pytest.approx(0.595, abs=1e-3)
        # skew: 0.8 * 0.90 * 0.8 = 0.576
        assert ts.scale_factors["skew_scale"] == pytest.approx(0.576, abs=1e-3)


# ======================================================================
# Effective strikes
# ======================================================================

class TestEffectiveStrikes:

    def test_clamp_lower_bound(self, rules):
        liq = LiquidityBoundary(strikes_ceiling=3)
        oi = OIAvailability(strikes_cap=None)
        assert _compute_effective_strikes(liq, oi, rules) == 7  # min clamp

    def test_clamp_upper_bound(self, rules):
        liq = LiquidityBoundary(strikes_ceiling=50)
        oi = OIAvailability(strikes_cap=None)
        assert _compute_effective_strikes(liq, oi, rules) == 31  # max clamp

    def test_oi_caps_below_liquidity(self, rules):
        liq = LiquidityBoundary(strikes_ceiling=17)
        oi = OIAvailability(strikes_cap=11)
        assert _compute_effective_strikes(liq, oi, rules) == 11


# ======================================================================
# Effective context priority
# ======================================================================

class TestEffectiveContext:

    def test_blocked_beats_all(self):
        conf = ConfidenceBoundary(recommended_context="blocked")
        temp = TemporalBoundary(earnings_window=True)
        assert _compute_effective_context(conf, temp, {"trade_permission": "允许"}) == "blocked"

    def test_event_beats_standard(self):
        conf = ConfidenceBoundary(recommended_context="standard")
        temp = TemporalBoundary(earnings_window=True)
        assert _compute_effective_context(conf, temp, {"trade_permission": "允许"}) == "event"

    def test_event_beats_minimum(self):
        conf = ConfidenceBoundary(recommended_context="minimum")
        temp = TemporalBoundary(earnings_window=True)
        assert _compute_effective_context(conf, temp, {"trade_permission": "允许"}) == "event"

    def test_permission_denied_blocked(self):
        conf = ConfidenceBoundary(recommended_context="standard")
        temp = TemporalBoundary(earnings_window=False)
        assert _compute_effective_context(conf, temp, {"trade_permission": "禁止"}) == "blocked"


# ======================================================================
# Swing overlay scenarios
# ======================================================================

class TestSwingOverlay:

    def test_high_vix(self):
        ms = {"vix": 35, "ivr": 50, "iv30": 40, "hv20": 30}
        so = _compute_swing_overlay(ms, BaseBoundary(), "偏多-买波")
        assert so.scenario == "high_vix"

    def test_normal(self):
        ms = {"vix": 17, "ivr": 45, "iv30": 30, "hv20": 28}
        so = _compute_swing_overlay(ms, BaseBoundary(), "偏多-买波")
        assert so.scenario == "normal"


# ======================================================================
# Vol range / VRP
# ======================================================================

class TestVolRange:

    def test_vrp_expanding(self):
        vr = _compute_vol_range({"iv30": 35, "hv20": 25}, {}, "偏多-买波")
        assert vr.vrp == pytest.approx(35 / 25, abs=1e-3)
        assert vr.vrp_regime == "EXPANDING"

    def test_vrp_compressing(self):
        vr = _compute_vol_range({"iv30": 20, "hv20": 30}, {}, "偏多-卖波")
        assert vr.vrp_regime == "COMPRESSING"

    def test_vrp_stable(self):
        vr = _compute_vol_range({"iv30": 30, "hv20": 30}, {}, "偏空-买波")
        assert vr.vrp_regime == "STABLE"

    def test_zero_hv(self):
        vr = _compute_vol_range({"iv30": 30, "hv20": 0}, {}, "偏多-买波")
        assert vr.vrp == 0.0


# ======================================================================
# Integration: full round trip via compute_micro_boundary
# ======================================================================

class TestRoundTrip:

    def test_json_serialisable(self):
        mb = compute_micro_boundary(_full_bridge())
        j = mb.to_json()
        restored = MicroBoundary.from_json(j)
        assert restored.ticker == "AAPL"
        assert restored.meso_state == "偏多-买波"

    def test_to_dict_from_dict(self):
        mb = compute_micro_boundary(_full_bridge())
        d = mb.to_dict()
        restored = MicroBoundary.from_dict(d)
        assert restored.effective_strikes == mb.effective_strikes
        assert restored.degradation.mode == mb.degradation.mode
