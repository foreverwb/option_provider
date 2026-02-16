"""
Volatility command entrypoints.
"""

from __future__ import annotations

from typing import Dict, List

from ..client import OratsClient
from ..config import DEFAULT_CONTRACT_FILTER, DEFAULT_METRIC, DEFAULT_VOL_DTE
from ..models import StrikeRow, VolatilityResult
from ..utils import (
    filter_by_dte,
    filter_by_expiration_type,
    parse_expiration_filter,
)
from .analyzer import analyze_skew, analyze_surface, analyze_term_structure


class VolatilityCommands:
    def __init__(self, orats_client: OratsClient):
        self.orats = orats_client

    def skew(
        self,
        symbol: str,
        metric: str = DEFAULT_METRIC,
        contract_filter: str = DEFAULT_CONTRACT_FILTER,
        dte: int = 98,
        expiration_filter: str = "*",
    ) -> VolatilityResult:
        summaries = self.orats.get_summaries(
            symbol,
            fields=(
                "ticker,tradeDate,skewing,contango,iv30d,iv60d,iv90d,"
                "dlt25Iv30d,dlt75Iv30d,dlt5Iv30d,dlt95Iv30d"
            ),
        )
        strikes = self.orats.get_strikes(
            symbol,
            dte=f"0,{dte}",
            fields=(
                "ticker,tradeDate,expirDate,dte,strike,stockPrice,spotPrice,"
                "callMidIv,putMidIv,callAskIv,putAskIv,smvVol,delta,gamma,vega,rho"
            ),
        )
        if not strikes:
            raise ValueError(f"No strikes data for {symbol}")

        exp_enum = parse_expiration_filter(expiration_filter)
        strikes = filter_by_dte(strikes, dte)
        strikes = filter_by_expiration_type(strikes, exp_enum)

        rows: List[StrikeRow] = [StrikeRow.from_orats(r) for r in strikes]
        summary = summaries[0] if summaries else {}
        data = analyze_skew(rows, summary, contract_filter=contract_filter)
        data["metric"] = metric

        as_of = str(summary.get("tradeDate") or rows[0].trade_date if rows else "")
        spot = float(rows[0].spot_price or rows[0].stock_price if rows else 0.0)

        return VolatilityResult(
            symbol=symbol.upper(),
            as_of=as_of,
            metric_name="skew",
            data=data,
            spot_price=spot,
            parameters={
                "metric": metric,
                "contract_filter": contract_filter,
                "dte": dte,
                "expiration_filter": expiration_filter,
            },
        )

    def term(
        self,
        symbol: str,
        dte: int = DEFAULT_VOL_DTE,
        expiration_filter: str = "*",
    ) -> VolatilityResult:
        summaries = self.orats.get_summaries(
            symbol,
            fields=(
                "ticker,tradeDate,iv10d,iv20d,iv30d,iv60d,iv90d,iv6m,iv1y,"
                "exErnIv30d,exErnIv60d,exErnIv90d,"
                "fwd30_20,fwd60_30,fwd90_30,fwd90_60,fwd180_90,contango"
            ),
        )
        monies = self.orats.get_monies_implied(
            symbol,
            fields="ticker,tradeDate,expirDate,dte,atmiv,slope,calVol",
        )

        exp_enum = parse_expiration_filter(expiration_filter)
        monies = [m for m in monies if int(m.get("dte", 0)) <= int(dte)]
        monies = filter_by_expiration_type(monies, exp_enum)

        summary = summaries[0] if summaries else {}
        data = analyze_term_structure(summary, monies)

        as_of = str(summary.get("tradeDate") or "")

        return VolatilityResult(
            symbol=symbol.upper(),
            as_of=as_of,
            metric_name="term",
            data=data,
            parameters={"dte": dte, "expiration_filter": expiration_filter},
        )

    def surface(
        self,
        symbol: str,
        metric: str = DEFAULT_METRIC,
        contract_filter: str = DEFAULT_CONTRACT_FILTER,
        dte: int = 98,
        expiration_filter: str = "*",
    ) -> VolatilityResult:
        strikes = self.orats.get_strikes(
            symbol,
            dte=f"0,{dte}",
            fields=(
                "ticker,tradeDate,expirDate,dte,strike,stockPrice,spotPrice,"
                "callMidIv,putMidIv,callAskIv,putAskIv,smvVol,delta,gamma,vega,rho"
            ),
        )
        if not strikes:
            raise ValueError(f"No strikes data for {symbol}")

        exp_enum = parse_expiration_filter(expiration_filter)
        strikes = filter_by_dte(strikes, dte)
        strikes = filter_by_expiration_type(strikes, exp_enum)

        rows: List[StrikeRow] = [StrikeRow.from_orats(r) for r in strikes]
        data = analyze_surface(rows, metric=metric, contract_filter=contract_filter)

        as_of = rows[0].trade_date if rows else ""
        spot = float(rows[0].spot_price or rows[0].stock_price if rows else 0.0)

        return VolatilityResult(
            symbol=symbol.upper(),
            as_of=as_of,
            metric_name="surface",
            data=data,
            spot_price=spot,
            parameters={
                "metric": metric,
                "contract_filter": contract_filter,
                "dte": dte,
                "expiration_filter": expiration_filter,
            },
        )
