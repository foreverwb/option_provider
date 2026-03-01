"""
Tests for MicroBoundary dataclass family (v3.0) and contract updates.
Each new dataclass gets 2 cases: normal (populated) and empty/missing.
"""

from __future__ import annotations

import json
import yaml
import pytest
from pathlib import Path

# ── models ──
from bridge_provider.models import (
    DirectionalRange, VolRange, LiquidityBoundary, OIAvailability,
    ConfidenceBoundary, TemporalBoundary, TermStructureBoundary,
    BaseBoundary, SwingOverlay, VolQuantOverlay, StrategyOverlay,
    Degradation, BoundaryMetadata, MicroBoundary,
    MESO_STATES, DEGRADATION_MODES, EFFECTIVE_CONTEXTS,
)

# ── contracts ──
from bridge_provider.contracts import (
    SwingBatchRow, SwingMarketParams, VolBatchRow,
)


# ======================================================================
# 1. DirectionalRange
# ======================================================================

class TestDirectionalRange:
    def test_normal(self):
        dr = DirectionalRange(upper=1.5, lower=-0.8, bias="bullish",
                              direction_score=0.72, direction_bias="偏多")
        d = dr.to_dict()
        assert d["upper"] == 1.5
        assert d["direction_bias"] == "偏多"
        restored = DirectionalRange.from_dict(d)
        assert restored.lower == -0.8

    def test_empty(self):
        dr = DirectionalRange.from_dict({})
        assert dr.upper is None
        d = dr.to_dict()
        assert json.dumps(d)  # JSON serialisable


# ======================================================================
# 2. VolRange
# ======================================================================

class TestVolRange:
    def test_normal(self):
        vr = VolRange(iv_current=0.28, iv_low=0.18, iv_high=0.55,
                      rv_ref=0.22, vrp=0.06, vrp_regime="positive",
                      ivr=0.45, vol_score=0.6, vol_bias="买波")
        d = vr.to_dict()
        assert d["vrp_regime"] == "positive"

    def test_empty(self):
        vr = VolRange.from_dict(None)
        assert vr.iv_current is None


# ======================================================================
# 3. LiquidityBoundary
# ======================================================================

class TestLiquidityBoundary:
    def test_normal(self):
        lb = LiquidityBoundary(raw_label="good", score=0.7, tier="good",
                               is_sufficient=True, strikes_ceiling=17,
                               active_open_ratio=1.2)
        assert lb.to_dict()["strikes_ceiling"] == 17

    def test_empty(self):
        lb = LiquidityBoundary.from_dict({})
        assert lb.raw_label is None
        assert lb.strikes_ceiling is None


# ======================================================================
# 4. OIAvailability
# ======================================================================

class TestOIAvailability:
    def test_normal(self):
        oi = OIAvailability(available=True, strikes_cap=21,
                            concentration={"put_wall": 4200, "call_wall": 4400})
        d = oi.to_dict()
        assert d["concentration"]["put_wall"] == 4200

    def test_empty(self):
        oi = OIAvailability.from_dict({})
        assert oi.available is None
        assert oi.concentration == {}


# ======================================================================
# 5. ConfidenceBoundary
# ======================================================================

class TestConfidenceBoundary:
    def test_normal(self):
        cb = ConfidenceBoundary(level=0.72, gate_passed=True,
                                gate_threshold=0.35,
                                recommended_context="standard",
                                notes="high conviction")
        assert cb.to_dict()["gate_passed"] is True

    def test_empty(self):
        cb = ConfidenceBoundary.from_dict({})
        assert cb.level is None


# ======================================================================
# 6. TemporalBoundary
# ======================================================================

class TestTemporalBoundary:
    def test_normal(self):
        tb = TemporalBoundary(earnings_window=True, days_to_earnings=5,
                              earnings_date="2026-03-15", dte_cluster="short",
                              is_index=False, is_squeeze=True)
        assert tb.to_dict()["is_squeeze"] is True

    def test_empty(self):
        tb = TemporalBoundary.from_dict(None)
        assert tb.earnings_window is None


# ======================================================================
# 7. TermStructureBoundary
# ======================================================================

class TestTermStructureBoundary:
    def test_normal(self):
        tsb = TermStructureBoundary(
            label_code="STEEP_CONTANGO", adjustment=0.12,
            horizon_bias={"gex": 1.0, "skew": 0.8},
            state_flags={"full_inversion": False},
            scale_factors={"gex_scale": 0.85},
        )
        d = tsb.to_dict()
        assert d["label_code"] == "STEEP_CONTANGO"

    def test_empty(self):
        tsb = TermStructureBoundary.from_dict({})
        assert tsb.horizon_bias == {}
        assert tsb.state_flags == {}


# ======================================================================
# 8. BaseBoundary
# ======================================================================

class TestBaseBoundary:
    def test_normal(self):
        bb = BaseBoundary(
            directional=DirectionalRange(upper=2.0),
            liquidity=LiquidityBoundary(strikes_ceiling=17),
        )
        d = bb.to_dict()
        assert d["directional"]["upper"] == 2.0
        assert d["liquidity"]["strikes_ceiling"] == 17
        restored = BaseBoundary.from_dict(d)
        assert restored.directional.upper == 2.0

    def test_empty(self):
        bb = BaseBoundary.from_dict({})
        assert bb.directional is None
        d = bb.to_dict()
        assert d["directional"] is None
        assert json.dumps(d)


# ======================================================================
# 9. SwingOverlay
# ======================================================================

class TestSwingOverlay:
    def test_normal(self):
        so = SwingOverlay(scenario="bull_spread",
                          suggested_dyn_params={"wing_width": 5})
        assert so.to_dict()["scenario"] == "bull_spread"

    def test_empty(self):
        so = SwingOverlay.from_dict({})
        assert so.scenario is None
        assert so.suggested_dyn_params == {}


# ======================================================================
# 10. VolQuantOverlay
# ======================================================================

class TestVolQuantOverlay:
    def test_normal(self):
        vo = VolQuantOverlay(gexbot_context="standard",
                             horizon_scales={"gex_scale": 0.85})
        assert vo.to_dict()["gexbot_context"] == "standard"

    def test_empty(self):
        vo = VolQuantOverlay.from_dict(None)
        assert vo.gexbot_context is None


# ======================================================================
# 11. StrategyOverlay
# ======================================================================

class TestStrategyOverlay:
    def test_normal(self):
        so = StrategyOverlay(
            swing=SwingOverlay(scenario="iron_condor"),
            vol_quant=VolQuantOverlay(gexbot_context="event"),
        )
        d = so.to_dict()
        assert d["swing"]["scenario"] == "iron_condor"
        restored = StrategyOverlay.from_dict(d)
        assert restored.vol_quant.gexbot_context == "event"

    def test_empty(self):
        so = StrategyOverlay.from_dict({})
        assert so.swing is None


# ======================================================================
# 12. Degradation
# ======================================================================

class TestDegradation:
    def test_normal(self):
        dg = Degradation(mode="partial",
                         missing_fields=["oi_data"],
                         fallback_rules_applied=["default_strikes"],
                         warnings=["OI data unavailable"])
        assert dg.to_dict()["mode"] == "partial"

    def test_empty(self):
        dg = Degradation.from_dict({})
        assert dg.mode is None
        assert dg.missing_fields == []


# ======================================================================
# 13. BoundaryMetadata
# ======================================================================

class TestBoundaryMetadata:
    def test_normal(self):
        md = BoundaryMetadata(data_completeness=0.95,
                              source_freshness="2026-02-28T10:00:00Z",
                              boundary_version="1.0",
                              rules_source="boundary_rules.yaml")
        assert md.to_dict()["boundary_version"] == "1.0"

    def test_empty(self):
        md = BoundaryMetadata.from_dict({})
        assert md.data_completeness is None


# ======================================================================
# 14. MicroBoundary (root)
# ======================================================================

class TestMicroBoundary:
    def test_full_round_trip(self):
        mb = MicroBoundary(
            ticker="AAPL",
            timestamp="2026-02-28T15:00:00Z",
            meso_state="偏多-买波",
            base_boundary=BaseBoundary(
                directional=DirectionalRange(upper=2.0, lower=-1.0),
                confidence=ConfidenceBoundary(level=0.72, gate_passed=True,
                                              gate_threshold=0.35,
                                              recommended_context="standard"),
                liquidity=LiquidityBoundary(raw_label="good", strikes_ceiling=17),
            ),
            effective_strikes=17,
            effective_context="standard",
            strategy_overlay=StrategyOverlay(
                vol_quant=VolQuantOverlay(gexbot_context="standard",
                                          horizon_scales={"gex_scale": 1.0}),
            ),
            degradation=Degradation(mode="full"),
            metadata=BoundaryMetadata(boundary_version="1.0"),
        )
        d = mb.to_dict()
        j = json.dumps(d)  # must be JSON serialisable
        assert json.loads(j)["ticker"] == "AAPL"

        restored = MicroBoundary.from_dict(d)
        assert restored.meso_state == "偏多-买波"
        assert restored.base_boundary.confidence.gate_passed is True
        assert restored.strategy_overlay.vol_quant.horizon_scales["gex_scale"] == 1.0

    def test_from_empty_dict(self):
        """Quality check: MicroBoundary.from_dict({}) must not raise."""
        mb = MicroBoundary.from_dict({})
        assert mb.ticker is None
        assert mb.base_boundary is None
        d = mb.to_dict()
        j = json.dumps(d)  # JSON serialisable
        assert json.loads(j)["effective_context"] is None

    def test_from_none(self):
        mb = MicroBoundary.from_dict(None)
        assert mb.ticker is None

    def test_json_round_trip(self):
        mb = MicroBoundary(ticker="SPY", meso_state="偏空-卖波",
                           effective_context="event", effective_strikes=13)
        restored = MicroBoundary.from_json(mb.to_json())
        assert restored.ticker == "SPY"
        assert restored.effective_strikes == 13


# ======================================================================
# Enum constants
# ======================================================================

class TestEnumConstants:
    def test_meso_states(self):
        assert "偏多-买波" in MESO_STATES
        assert "偏空-卖波" in MESO_STATES
        assert len(MESO_STATES) == 4

    def test_degradation_modes(self):
        assert "full" in DEGRADATION_MODES
        assert "blocked" in DEGRADATION_MODES

    def test_effective_contexts(self):
        assert "standard" in EFFECTIVE_CONTEXTS
        assert "blocked" in EFFECTIVE_CONTEXTS


# ======================================================================
# Contract backward compatibility
# ======================================================================

class TestContractBackwardCompat:
    def test_swing_row_without_micro_boundary(self):
        """SwingBatchRow must still construct without micro_boundary."""
        row = SwingBatchRow(
            symbol="AAPL",
            market_params=SwingMarketParams(
                vix=18.5, ivr=0.45, iv30=0.28, hv20=0.22,
                iv_path="elevated",
            ),
            bridge={"direction_score": 0.7},
        )
        assert row.micro_boundary is None

    def test_swing_row_with_micro_boundary(self):
        mb = MicroBoundary(ticker="AAPL", effective_context="standard").to_dict()
        row = SwingBatchRow(
            symbol="AAPL",
            market_params=SwingMarketParams(
                vix=18.5, ivr=0.45, iv30=0.28, hv20=0.22,
                iv_path="elevated",
            ),
            bridge={},
            micro_boundary=mb,
        )
        assert row.micro_boundary["ticker"] == "AAPL"

    def test_vol_row_without_micro_boundary(self):
        row = VolBatchRow(symbol="TSLA", bridge={"vol_score": 0.3})
        assert row.micro_boundary is None

    def test_vol_row_with_micro_boundary(self):
        mb = MicroBoundary(ticker="TSLA", meso_state="偏空-买波").to_dict()
        row = VolBatchRow(symbol="TSLA", bridge={}, micro_boundary=mb)
        assert row.micro_boundary["meso_state"] == "偏空-买波"


# ======================================================================
# boundary_rules.yaml parsability
# ======================================================================

class TestBoundaryRulesYaml:
    @pytest.fixture
    def rules(self):
        yaml_path = Path(__file__).resolve().parent.parent / "bridge_provider" / "boundary_rules.yaml"
        with open(yaml_path) as f:
            return yaml.safe_load(f)

    def test_yaml_loads(self, rules):
        assert rules["version"] == "1.0"

    def test_liquidity_strikes_map(self, rules):
        sm = rules["liquidity"]["strikes_map"]
        assert sm["excellent"] == 21
        assert sm["poor"] == 9

    def test_confidence_gates(self, rules):
        c = rules["confidence"]
        assert c["buy_vol_min"] == 0.35
        assert c["sell_vol_min"] == 0.50
        assert c["blocked_threshold"] == 0.20

    def test_clamps(self, rules):
        cl = rules["clamps"]
        assert cl["strikes"]["min"] == 7
        assert cl["strikes"]["max"] == 31

    def test_degradation_priority(self, rules):
        dp = rules["degradation"]["mode_priority"]
        assert dp[0] == "blocked"
        assert dp[-1] == "full"

    def test_term_structure_overrides(self, rules):
        so = rules["term_structure"]["horizon_multipliers"]["state_overrides"]
        assert "full_inversion" in so
        assert so["full_inversion"]["gex_scale"] == 0.7
