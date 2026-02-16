from __future__ import annotations

from typing import Any, Dict, List

from orats_provider.greeks_exposure.commands import GreeksExposureCommands


class FakeOratsClient:
    def __init__(self, strikes: List[Dict[str, Any]]):
        self._strikes = strikes

    def get_strikes(self, ticker: str, dte: str | None = None, fields: str | None = None) -> List[Dict[str, Any]]:
        return list(self._strikes)


def test_gex_returns_valid_result(mock_orats_strikes: List[Dict[str, Any]]) -> None:
    commands = GreeksExposureCommands(FakeOratsClient(mock_orats_strikes))
    result = commands.gex("AAPL", strikes=15, dte=98, expiration_filter="*")

    assert result.metric_name == "gex"
    assert isinstance(result.total_exposure, float)
    assert len(result.by_strike) > 0
    assert result.spot_price > 0


def test_gexn_finds_gamma_flip(mock_orats_strikes: List[Dict[str, Any]]) -> None:
    commands = GreeksExposureCommands(FakeOratsClient(mock_orats_strikes))
    result = commands.gexn("AAPL", strikes=15, dte=98, expiration_filter="*")

    assert result.metric_name == "gexn"
    assert result.gamma_flip_strike is not None
    assert 180.0 <= float(result.gamma_flip_strike) <= 210.0


def test_vanna_returns_nonempty_payload(mock_orats_strikes: List[Dict[str, Any]]) -> None:
    commands = GreeksExposureCommands(FakeOratsClient(mock_orats_strikes))
    result = commands.vanna("AAPL", strikes=15, dte=98, expiration_filter="*")

    assert result.metric_name == "vanna"
    assert len(result.by_strike) > 0
