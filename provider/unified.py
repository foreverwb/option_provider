"""
Unified provider: bridge client + ORATS command sets.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from bridge_client.client import BridgeClient
from bridge_client.micro_templates import select_micro_template
from bridge_client.models import BridgeSnapshot
from orats_provider.client import OratsClient
from orats_provider.greeks_exposure.commands import GreeksExposureCommands
from orats_provider.models import ExposureResult, VolatilityResult
from orats_provider.volatility.commands import VolatilityCommands


class UnifiedProvider:
    """
    One-stop provider for bridge snapshots and ORATS metrics.
    """

    def __init__(
        self,
        va_base_url: str = "http://localhost:8668",
        orats_token: Optional[str] = None,
    ) -> None:
        self.bridge = BridgeClient(base_url=va_base_url)
        self.orats = OratsClient(token=orats_token)
        self.greeks = GreeksExposureCommands(self.orats)
        self.vol = VolatilityCommands(self.orats)

    # Bridge
    def get_bridge_snapshot(self, symbol: str, date: Optional[str] = None) -> BridgeSnapshot:
        return self.bridge.get_bridge_snapshot(symbol, date=date)

    def get_micro_template(
        self, symbol: str, date: Optional[str] = None, cfg: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        snapshot = self.get_bridge_snapshot(symbol, date)
        return select_micro_template(snapshot, cfg or {})

    def get_bridge_batch(
        self,
        symbols: Optional[List[str]] = None,
        date: Optional[str] = None,
        source: str = "swing",
        min_direction_score: float = 1.0,
        min_vol_score: float = 0.8,
        limit: int = 50,
    ) -> Dict[str, Any]:
        return self.bridge.get_bridge_batch(
            symbols=symbols,
            date=date,
            source=source,
            min_direction_score=min_direction_score,
            min_vol_score=min_vol_score,
            limit=limit,
        )

    # Greeks
    def gex(self, symbol: str, **kwargs: Any) -> ExposureResult:
        return self.greeks.gex(symbol, **kwargs)

    def gexn(self, symbol: str, **kwargs: Any) -> ExposureResult:
        return self.greeks.gexn(symbol, **kwargs)

    def gexr(self, symbol: str, **kwargs: Any) -> ExposureResult:
        return self.greeks.gexr(symbol, **kwargs)

    def gexs(self, symbol: str, **kwargs: Any) -> ExposureResult:
        return self.greeks.gexs(symbol, **kwargs)

    def dex(self, symbol: str, **kwargs: Any) -> ExposureResult:
        return self.greeks.dex(symbol, **kwargs)

    def dexn(self, symbol: str, **kwargs: Any) -> ExposureResult:
        return self.greeks.dexn(symbol, **kwargs)

    def vex(self, symbol: str, **kwargs: Any) -> ExposureResult:
        return self.greeks.vex(symbol, **kwargs)

    def vexn(self, symbol: str, **kwargs: Any) -> ExposureResult:
        return self.greeks.vexn(symbol, **kwargs)

    def vanna(self, symbol: str, **kwargs: Any) -> ExposureResult:
        return self.greeks.vanna(symbol, **kwargs)

    # Volatility
    def skew(self, symbol: str, **kwargs: Any) -> VolatilityResult:
        return self.vol.skew(symbol, **kwargs)

    def term(self, symbol: str, **kwargs: Any) -> VolatilityResult:
        return self.vol.term(symbol, **kwargs)

    def surface(self, symbol: str, **kwargs: Any) -> VolatilityResult:
        return self.vol.surface(symbol, **kwargs)

    # Combined
    def full_analysis(self, symbol: str, date: Optional[str] = None) -> Dict[str, Any]:
        snapshot = self.get_bridge_snapshot(symbol, date)
        gex_result = self.gex(symbol)
        term_result = self.term(symbol)
        skew_result = self.skew(symbol)

        return {
            "symbol": symbol.upper(),
            "bridge": snapshot.to_dict(),
            "greeks": {"gex": gex_result.to_dict()},
            "volatility": {
                "term": term_result.to_dict(),
                "skew": skew_result.to_dict(),
            },
        }

    def close(self) -> None:
        self.bridge.close()
        self.orats.close()

    def __enter__(self) -> "UnifiedProvider":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()
