"""
Tests for Greeks exposure calculations — formula verification, gamma flip, commands.
"""

import pytest
from typing import List

from orats_provider.models import StrikeRecord, GreeksExposureResult
from orats_provider.greeks_exposure import calculator
from orats_provider.greeks_exposure.commands import execute_from_records, COMMANDS
from orats_provider.greeks_exposure.formatter import to_json, to_summary, to_chart_data


# ── Precise formula verification ───────────────────────────────────────

class TestGEXFormula:
    """Verify GEX formula with known inputs."""

    def test_single_strike_gex(self):
        rec = StrikeRecord(
            strike=150.0, spot_price=150.0,
            call_gamma=0.04, put_gamma=0.04,
            call_oi=5000, put_oi=6000,
        )
        result = calculator.compute_gex_per_strike([rec])
        assert len(result) == 1
        entry = result[0]

        # GEX_call = 0.04 × 5000 × 150² × 0.01 × 100 = 0.04 × 5000 × 22500 × 1 = 4,500,000
        expected_call = 0.04 * 5000 * (150 ** 2) * 0.01 * 100
        assert abs(entry["gex_call"] - expected_call) < 1.0

        # GEX_put = -0.04 × 6000 × 150² × 0.01 × 100 = -5,400,000
        expected_put = -0.04 * 6000 * (150 ** 2) * 0.01 * 100
        assert abs(entry["gex_put"] - expected_put) < 1.0

    def test_net_gex(self, strike_chain):
        net = calculator.compute_net_gex(strike_chain)
        assert isinstance(net, float)

    def test_gex_distribution(self, strike_chain):
        dist = calculator.compute_gex_distribution(strike_chain)
        assert len(dist) > 0
        assert all("strike" in d and "net_gex" in d for d in dist)


class TestDEXFormula:
    """Verify DEX formula."""

    def test_single_strike_dex(self):
        rec = StrikeRecord(
            strike=150.0, spot_price=150.0,
            call_delta=0.50, put_delta=-0.50,
            call_oi=5000, put_oi=6000,
        )
        result = calculator.compute_dex_per_strike([rec])
        entry = result[0]

        expected_call = 0.50 * 5000 * 150.0 * 100
        expected_put = -0.50 * 6000 * 150.0 * 100
        assert abs(entry["dex_call"] - expected_call) < 1.0
        assert abs(entry["dex_put"] - expected_put) < 1.0

    def test_net_dex(self, strike_chain):
        net = calculator.compute_net_dex(strike_chain)
        assert isinstance(net, float)


class TestVEXFormula:
    """Verify VEX formula."""

    def test_single_strike_vex(self):
        rec = StrikeRecord(
            strike=150.0, spot_price=150.0,
            call_vega=0.20, put_vega=0.20,
            call_oi=5000, put_oi=6000,
        )
        result = calculator.compute_vex_per_strike([rec])
        entry = result[0]

        expected_call = 0.20 * 5000 * 100
        expected_put = 0.20 * 6000 * 100
        assert abs(entry["vex_call"] - expected_call) < 1.0
        assert abs(entry["vex_put"] - expected_put) < 1.0

    def test_net_vex(self, strike_chain):
        net = calculator.compute_net_vex(strike_chain)
        assert isinstance(net, float)


class TestVannaFormula:
    """Verify Vanna formula."""

    def test_single_strike_vanna(self):
        rec = StrikeRecord(
            strike=150.0, spot_price=150.0,
            call_vanna=0.01, put_vanna=-0.008,
            call_oi=5000, put_oi=6000,
        )
        result = calculator.compute_vanna_per_strike([rec])
        entry = result[0]

        expected_call = 0.01 * 5000 * 100
        expected_put = -0.008 * 6000 * 100
        assert abs(entry["vanna_call"] - expected_call) < 1.0
        assert abs(entry["vanna_put"] - expected_put) < 1.0

    def test_net_vanna(self, strike_chain):
        net = calculator.compute_net_vanna(strike_chain)
        assert isinstance(net, float)


# ── GEX 3D ──────────────────────────────────────────────────────────────

class TestGEX3D:
    def test_gex_3d(self, strike_chain):
        matrix = calculator.compute_gex_3d(strike_chain)
        assert len(matrix) == len(strike_chain)
        assert all("dte" in d for d in matrix)


# ── Command dispatch ────────────────────────────────────────────────────

class TestGreeksCommands:
    @pytest.mark.parametrize("cmd", COMMANDS)
    def test_all_commands(self, cmd, strike_chain):
        result = execute_from_records(cmd, "AAPL", strike_chain)
        assert isinstance(result, GreeksExposureResult)
        assert result.symbol == "AAPL"
        assert result.command == cmd

    def test_unknown_command(self, strike_chain):
        with pytest.raises(ValueError, match="Unknown"):
            execute_from_records("invalid_cmd", "AAPL", strike_chain)

    def test_gex_command_has_gamma_flip(self, strike_chain):
        result = execute_from_records("gex", "AAPL", strike_chain)
        assert "gamma_flip_strike" in result.summary

    def test_net_gex_command(self, strike_chain):
        result = execute_from_records("net_gex", "AAPL", strike_chain)
        assert "net_gex" in result.data


# ── Formatter ───────────────────────────────────────────────────────────

class TestGreeksFormatter:
    def test_to_json(self, strike_chain):
        result = execute_from_records("gex", "AAPL", strike_chain)
        j = to_json(result)
        assert "AAPL" in j

    def test_to_summary(self, strike_chain):
        result = execute_from_records("net_gex", "AAPL", strike_chain)
        s = to_summary(result)
        assert "NET_GEX" in s
        assert "AAPL" in s

    def test_to_chart_data_bar(self, strike_chain):
        result = execute_from_records("gex", "AAPL", strike_chain)
        chart = to_chart_data(result)
        assert chart["type"] == "bar"

    def test_to_chart_data_surface(self, strike_chain):
        result = execute_from_records("gex_3d", "AAPL", strike_chain)
        chart = to_chart_data(result)
        assert chart["type"] == "surface"

    def test_to_chart_data_scalar(self, strike_chain):
        result = execute_from_records("net_gex", "AAPL", strike_chain)
        chart = to_chart_data(result)
        assert chart["type"] == "scalar"
