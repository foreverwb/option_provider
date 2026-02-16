from __future__ import annotations

from typing import Any, Dict, List

from orats_provider.volatility.commands import VolatilityCommands


class FakeOratsClient:
    def __init__(
        self,
        strikes: List[Dict[str, Any]],
        summaries: List[Dict[str, Any]],
        monies: List[Dict[str, Any]],
    ) -> None:
        self._strikes = strikes
        self._summaries = summaries
        self._monies = monies

    def get_strikes(self, ticker: str, dte: str | None = None, fields: str | None = None) -> List[Dict[str, Any]]:
        return list(self._strikes)

    def get_summaries(self, ticker: str, fields: str | None = None) -> List[Dict[str, Any]]:
        return list(self._summaries)

    def get_monies_implied(self, ticker: str, fields: str | None = None) -> List[Dict[str, Any]]:
        return list(self._monies)


def test_skew_calculation(
    mock_orats_strikes: List[Dict[str, Any]],
    mock_orats_summaries: List[Dict[str, Any]],
    mock_orats_monies: List[Dict[str, Any]],
) -> None:
    commands = VolatilityCommands(
        FakeOratsClient(mock_orats_strikes, mock_orats_summaries, mock_orats_monies)
    )
    result = commands.skew("AAPL", contract_filter="ntm", dte=98, expiration_filter="*")

    assert result.metric_name == "skew"
    assert "overall_skew" in result.data
    assert len(result.data.get("by_expiry", [])) > 0


def test_term_calculation(
    mock_orats_strikes: List[Dict[str, Any]],
    mock_orats_summaries: List[Dict[str, Any]],
    mock_orats_monies: List[Dict[str, Any]],
) -> None:
    commands = VolatilityCommands(
        FakeOratsClient(mock_orats_strikes, mock_orats_summaries, mock_orats_monies)
    )
    result = commands.term("AAPL", dte=365, expiration_filter="*")

    assert result.metric_name == "term"
    assert result.data.get("state") in {"contango", "backwardation", "mixed", "unknown"}
    assert len(result.data.get("implied_curve", [])) > 0


def test_surface_dimensions(
    mock_orats_strikes: List[Dict[str, Any]],
    mock_orats_summaries: List[Dict[str, Any]],
    mock_orats_monies: List[Dict[str, Any]],
) -> None:
    commands = VolatilityCommands(
        FakeOratsClient(mock_orats_strikes, mock_orats_summaries, mock_orats_monies)
    )
    result = commands.surface("AAPL", metric="VOLATILITY_MID", dte=98, expiration_filter="*")

    expiries = result.data.get("expiries", [])
    strikes = result.data.get("strikes", [])
    matrix = result.data.get("matrix", [])

    assert result.metric_name == "surface"
    assert len(expiries) > 0
    assert len(strikes) > 0
    assert len(matrix) == len(expiries)
