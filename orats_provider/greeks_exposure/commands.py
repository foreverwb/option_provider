"""
Greeks exposure command entrypoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..client import OratsClient
from ..config import DEFAULT_DTE, DEFAULT_EXPIRATION_FILTER, DEFAULT_STRIKES_RANGE
from ..models import ExpirationFilter, ExposureResult, StrikeRow
from ..utils import (
    filter_by_dte,
    filter_by_expiration_type,
    filter_by_strikes_range,
    parse_expiration_filter,
)
from .calculator import (
    compute_delta_exposure,
    compute_gamma_3d,
    compute_gamma_by_strike,
    compute_gamma_exposure,
    compute_net_delta,
    compute_net_gamma,
    compute_net_vega,
    compute_vanna_exposure,
    compute_vega_exposure,
)


class GreeksExposureCommands:
    def __init__(self, orats_client: OratsClient):
        self.orats = orats_client

    def _fetch_and_filter(
        self,
        symbol: str,
        strikes: int = DEFAULT_STRIKES_RANGE,
        dte: int = DEFAULT_DTE,
        expiration_filter: str = DEFAULT_EXPIRATION_FILTER,
    ) -> Tuple[List[StrikeRow], float, str]:
        raw = self.orats.get_strikes(
            ticker=symbol.upper(),
            dte=f"0,{dte}",
            fields=(
                "ticker,tradeDate,expirDate,dte,strike,stockPrice,"
                "callVolume,callOpenInterest,putVolume,putOpenInterest,"
                "callMidIv,putMidIv,smvVol,delta,gamma,theta,vega,rho,spotPrice"
            ),
        )
        if not raw:
            raise ValueError(f"No strikes data for {symbol}")

        spot_price = float(raw[0].get("spotPrice") or raw[0].get("stockPrice") or 0.0)
        rows_dict = filter_by_dte(raw, dte)
        rows_dict = filter_by_strikes_range(rows_dict, spot_price, strikes)

        exp_enum: ExpirationFilter = parse_expiration_filter(expiration_filter)
        rows_dict = filter_by_expiration_type(rows_dict, exp_enum)
        if not rows_dict:
            raise ValueError(
                f"No strikes left after filters for {symbol} (dte={dte}, expiration_filter={expiration_filter})"
            )

        rows = [StrikeRow.from_orats(r) for r in rows_dict]
        as_of = rows[0].trade_date if rows else ""
        return rows, spot_price, as_of

    def gex(
        self,
        symbol: str,
        strikes: int = DEFAULT_STRIKES_RANGE,
        dte: int = DEFAULT_DTE,
        expiration_filter: str = DEFAULT_EXPIRATION_FILTER,
    ) -> ExposureResult:
        data, spot, as_of = self._fetch_and_filter(symbol, strikes, dte, expiration_filter)
        result = compute_gamma_exposure(data, spot)
        return ExposureResult(
            symbol=symbol.upper(),
            as_of=as_of,
            metric_name="gex",
            total_exposure=result["total_gex"],
            net_exposure=result["total_gex"],
            by_strike=result["by_strike"],
            by_expiry=result.get("by_expiry", []),
            spot_price=spot,
            parameters={"strikes": strikes, "dte": dte, "expiration_filter": expiration_filter},
        )

    def gexn(
        self,
        symbol: str,
        strikes: int = DEFAULT_STRIKES_RANGE,
        dte: int = DEFAULT_DTE,
        expiration_filter: str = DEFAULT_EXPIRATION_FILTER,
    ) -> ExposureResult:
        data, spot, as_of = self._fetch_and_filter(symbol, strikes, dte, expiration_filter)
        result = compute_net_gamma(data, spot)
        return ExposureResult(
            symbol=symbol.upper(),
            as_of=as_of,
            metric_name="gexn",
            total_exposure=result["total_gex"],
            net_exposure=result["total_gex"],
            by_strike=result["by_strike"],
            by_expiry=result.get("by_expiry", []),
            gamma_flip_strike=result.get("gamma_flip_strike"),
            spot_price=spot,
            parameters={"strikes": strikes, "dte": dte, "expiration_filter": expiration_filter},
        )

    def gexr(
        self,
        symbol: str,
        strikes: int = DEFAULT_STRIKES_RANGE,
        dte: int = DEFAULT_DTE,
        expiration_filter: str = DEFAULT_EXPIRATION_FILTER,
    ) -> ExposureResult:
        data, spot, as_of = self._fetch_and_filter(symbol, strikes, dte, expiration_filter)
        result = compute_gamma_by_strike(data, spot)
        return ExposureResult(
            symbol=symbol.upper(),
            as_of=as_of,
            metric_name="gexr",
            total_exposure=result["total_gex"],
            net_exposure=result["total_gex"],
            by_strike=result["by_strike"],
            spot_price=spot,
            parameters={
                "strikes": strikes,
                "dte": dte,
                "expiration_filter": expiration_filter,
                "magnet_strike": result.get("magnet_strike"),
            },
        )

    def gexs(
        self,
        symbol: str,
        strikes: int = DEFAULT_STRIKES_RANGE,
        dte: int = DEFAULT_DTE,
        expiration_filter: str = DEFAULT_EXPIRATION_FILTER,
    ) -> ExposureResult:
        data, spot, as_of = self._fetch_and_filter(symbol, strikes, dte, expiration_filter)
        result = compute_gamma_3d(data, spot)
        total = sum(float(item.get("net_gex", 0.0)) for item in result.get("points", []))
        return ExposureResult(
            symbol=symbol.upper(),
            as_of=as_of,
            metric_name="gexs",
            total_exposure=total,
            net_exposure=total,
            by_strike=result.get("points", []),
            by_expiry=result.get("by_expiry", []),
            spot_price=spot,
            parameters={"strikes": strikes, "dte": dte, "expiration_filter": expiration_filter},
        )

    # Common aliases used in some tables/UI docs.
    def sgex(self, symbol: str, strikes: int = 15, dte: int = 98, expiration_filter: str = "*") -> ExposureResult:
        return self.gexs(symbol, strikes=strikes, dte=dte, expiration_filter=expiration_filter)

    def sagex(
        self, symbol: str, strikes: int = 15, dte: int = 98, expiration_filter: str = "*"
    ) -> ExposureResult:
        return self.gexs(symbol, strikes=strikes, dte=dte, expiration_filter=expiration_filter)

    def dex(
        self,
        symbol: str,
        strikes: int = DEFAULT_STRIKES_RANGE,
        dte: int = DEFAULT_DTE,
        expiration_filter: str = DEFAULT_EXPIRATION_FILTER,
    ) -> ExposureResult:
        data, spot, as_of = self._fetch_and_filter(symbol, strikes, dte, expiration_filter)
        result = compute_delta_exposure(data)
        return ExposureResult(
            symbol=symbol.upper(),
            as_of=as_of,
            metric_name="dex",
            total_exposure=result["total_dex"],
            net_exposure=result["total_dex"],
            by_strike=result["by_strike"],
            spot_price=spot,
            parameters={"strikes": strikes, "dte": dte, "expiration_filter": expiration_filter},
        )

    def dexn(
        self,
        symbol: str,
        strikes: int = DEFAULT_STRIKES_RANGE,
        dte: int = DEFAULT_DTE,
        expiration_filter: str = DEFAULT_EXPIRATION_FILTER,
    ) -> ExposureResult:
        data, spot, as_of = self._fetch_and_filter(symbol, strikes, dte, expiration_filter)
        result = compute_net_delta(data)
        return ExposureResult(
            symbol=symbol.upper(),
            as_of=as_of,
            metric_name="dexn",
            total_exposure=result["total_dex"],
            net_exposure=result["net_dex"],
            by_strike=result["by_strike"],
            spot_price=spot,
            parameters={"strikes": strikes, "dte": dte, "expiration_filter": expiration_filter},
        )

    def vex(
        self,
        symbol: str,
        strikes: int = DEFAULT_STRIKES_RANGE,
        dte: int = DEFAULT_DTE,
        expiration_filter: str = DEFAULT_EXPIRATION_FILTER,
    ) -> ExposureResult:
        data, spot, as_of = self._fetch_and_filter(symbol, strikes, dte, expiration_filter)
        result = compute_vega_exposure(data)
        return ExposureResult(
            symbol=symbol.upper(),
            as_of=as_of,
            metric_name="vex",
            total_exposure=result["total_vex"],
            net_exposure=result["total_vex"],
            by_strike=result["by_strike"],
            spot_price=spot,
            parameters={"strikes": strikes, "dte": dte, "expiration_filter": expiration_filter},
        )

    def vexn(
        self,
        symbol: str,
        strikes: int = DEFAULT_STRIKES_RANGE,
        dte: int = DEFAULT_DTE,
        expiration_filter: str = DEFAULT_EXPIRATION_FILTER,
    ) -> ExposureResult:
        data, spot, as_of = self._fetch_and_filter(symbol, strikes, dte, expiration_filter)
        result = compute_net_vega(data)
        return ExposureResult(
            symbol=symbol.upper(),
            as_of=as_of,
            metric_name="vexn",
            total_exposure=result["total_call_vex"] + result["total_put_vex"],
            net_exposure=result["total_net_vex"],
            by_strike=result["by_strike"],
            spot_price=spot,
            parameters={"strikes": strikes, "dte": dte, "expiration_filter": expiration_filter},
        )

    def vanna(
        self,
        symbol: str,
        strikes: int = DEFAULT_STRIKES_RANGE,
        dte: int = DEFAULT_DTE,
        expiration_filter: str = DEFAULT_EXPIRATION_FILTER,
    ) -> ExposureResult:
        data, spot, as_of = self._fetch_and_filter(symbol, strikes, dte, expiration_filter)
        result = compute_vanna_exposure(data, spot)
        return ExposureResult(
            symbol=symbol.upper(),
            as_of=as_of,
            metric_name="vanna",
            total_exposure=result["total_vanna_exp"],
            net_exposure=result["total_vanna_exp"],
            by_strike=result["by_strike"],
            spot_price=spot,
            parameters={"strikes": strikes, "dte": dte, "expiration_filter": expiration_filter},
        )
