"""
Tests for volatility analysis — skew, term structure, surface, contango detection.
"""

import pytest
from typing import List

from orats_provider.models import StrikeRecord, VolatilityResult
from orats_provider.volatility import analyzer
from orats_provider.volatility.commands import execute_from_records, COMMANDS
from orats_provider.volatility.formatter import to_json, to_summary, to_chart_data


# ── Skew Analysis ───────────────────────────────────────────────────────

class TestSkewAnalysis:
    def test_skew_by_expiry(self, strike_chain):
        skew = analyzer.compute_skew_by_expiry(strike_chain)
        assert len(skew) == 3  # 3 expiry dates
        for entry in skew:
            assert "skew" in entry
            assert "avg_put_iv" in entry
            assert "avg_call_iv" in entry
            # Put skew typically positive (puts > calls for OTM)
            assert isinstance(entry["skew"], float)

    def test_skew_positive(self, strike_chain):
        """OTM puts should have higher IV than OTM calls (positive skew)."""
        skew = analyzer.compute_skew_by_expiry(strike_chain)
        # At least some expiries should show positive skew
        positive_skew = [s for s in skew if s["skew"] > 0]
        assert len(positive_skew) > 0, "Expected positive skew in synthetic data"

    def test_smile_curve(self, strike_chain):
        smile = analyzer.compute_smile(strike_chain, "2026-03-20")
        assert len(smile) > 0
        for point in smile:
            assert "strike" in point
            assert "mid_iv" in point
            assert "moneyness" in point

    def test_smile_empty_expiry(self, strike_chain):
        smile = analyzer.compute_smile(strike_chain, "2099-01-01")
        assert smile == []


# ── Term Structure Analysis ─────────────────────────────────────────────

class TestTermStructure:
    def test_by_expiry(self, strike_chain):
        term = analyzer.compute_term_structure_by_expiry(strike_chain)
        assert len(term) >= 2
        for entry in term:
            assert "dte" in entry
            assert "atm_iv" in entry
            assert entry["atm_iv"] > 0

    def test_contango_detection(self, strike_chain):
        """Synthetic data has contango shape (front < back)."""
        term = analyzer.compute_term_structure_by_expiry(strike_chain)
        state = analyzer.detect_contango_state(term)
        assert state["state"] in ("CONTANGO", "FLAT", "BACKWARDATION")
        assert state["ratio"] is not None
        assert state["front_iv"] is not None
        assert state["back_iv"] is not None

    def test_contango_state_synthetic(self, strike_chain):
        """Our synthetic data has contango (front IV < back IV)."""
        term = analyzer.compute_term_structure_by_expiry(strike_chain)
        state = analyzer.detect_contango_state(term)
        # Synthetic data: base_iv = 0.25 + 0.08*(i_exp/3), so front < back
        assert state["state"] == "CONTANGO"
        assert state["ratio"] < 1.0

    def test_backwardation_detection(self):
        """Manually construct backwardation data."""
        term_data = [
            {"dte": 30, "atm_iv": 0.40},
            {"dte": 60, "atm_iv": 0.30},
        ]
        state = analyzer.detect_contango_state(term_data)
        assert state["state"] == "BACKWARDATION"
        assert state["ratio"] > 1.0

    def test_flat_detection(self):
        term_data = [
            {"dte": 30, "atm_iv": 0.30},
            {"dte": 60, "atm_iv": 0.305},
        ]
        state = analyzer.detect_contango_state(term_data)
        assert state["state"] == "FLAT"

    def test_constant_maturity_iv(self, strike_chain):
        term = analyzer.compute_term_structure_by_expiry(strike_chain)
        iv30 = analyzer.compute_constant_maturity_iv(term, target_dte=30)
        assert iv30 is not None
        assert 0.05 < iv30 < 1.0

    def test_constant_maturity_interpolation(self):
        term_data = [
            {"dte": 20, "atm_iv": 0.25},
            {"dte": 40, "atm_iv": 0.30},
        ]
        iv30 = analyzer.compute_constant_maturity_iv(term_data, target_dte=30)
        assert iv30 is not None
        assert abs(iv30 - 0.275) < 0.001  # Linear interpolation midpoint

    def test_constant_maturity_empty(self):
        assert analyzer.compute_constant_maturity_iv([], 30) is None

    def test_unknown_state_single_expiry(self):
        state = analyzer.detect_contango_state([{"dte": 30, "atm_iv": 0.25}])
        assert state["state"] == "UNKNOWN"


# ── Surface Analysis ───────────────────────────────────────────────────

class TestSurface:
    def test_vol_surface(self, strike_chain):
        surface = analyzer.compute_vol_surface(strike_chain)
        assert len(surface) == len(strike_chain)
        for point in surface:
            assert "strike" in point
            assert "dte" in point
            assert "mid_iv" in point
            assert "moneyness" in point

    def test_surface_sorted(self, strike_chain):
        surface = analyzer.compute_vol_surface(strike_chain)
        # Should be sorted by (dte, strike)
        for i in range(1, len(surface)):
            prev = (surface[i - 1]["dte"], surface[i - 1]["strike"])
            curr = (surface[i]["dte"], surface[i]["strike"])
            assert prev <= curr


# ── Command dispatch ────────────────────────────────────────────────────

class TestVolatilityCommands:
    @pytest.mark.parametrize("cmd", COMMANDS)
    def test_all_commands(self, cmd, strike_chain):
        result = execute_from_records(cmd, "AAPL", strike_chain)
        assert isinstance(result, VolatilityResult)
        assert result.symbol == "AAPL"
        assert result.command == cmd

    def test_unknown_command(self, strike_chain):
        with pytest.raises(ValueError, match="Unknown"):
            execute_from_records("invalid", "AAPL", strike_chain)

    def test_skew_with_expiry(self, strike_chain):
        result = execute_from_records("skew", "AAPL", strike_chain, expiry_date="2026-03-20")
        assert result.data["smile"] is not None
        assert len(result.data["smile"]) > 0

    def test_term_contango_state(self, strike_chain):
        result = execute_from_records("term", "AAPL", strike_chain)
        assert "state" in result.summary

    def test_surface_metadata(self, strike_chain):
        result = execute_from_records("surface", "AAPL", strike_chain)
        assert result.summary["num_points"] > 0


# ── Formatter ───────────────────────────────────────────────────────────

class TestVolatilityFormatter:
    def test_to_json(self, strike_chain):
        result = execute_from_records("skew", "AAPL", strike_chain)
        j = to_json(result)
        assert "AAPL" in j

    def test_to_summary(self, strike_chain):
        result = execute_from_records("term", "AAPL", strike_chain)
        s = to_summary(result)
        assert "TERM" in s

    def test_chart_skew_by_expiry(self, strike_chain):
        result = execute_from_records("skew", "AAPL", strike_chain)
        chart = to_chart_data(result)
        assert chart["type"] == "bar"

    def test_chart_smile(self, strike_chain):
        result = execute_from_records("skew", "AAPL", strike_chain, expiry_date="2026-03-20")
        chart = to_chart_data(result)
        assert chart["type"] == "line"

    def test_chart_term(self, strike_chain):
        result = execute_from_records("term", "AAPL", strike_chain)
        chart = to_chart_data(result)
        assert chart["type"] == "line"

    def test_chart_surface(self, strike_chain):
        result = execute_from_records("surface", "AAPL", strike_chain)
        chart = to_chart_data(result)
        assert chart["type"] == "surface"
