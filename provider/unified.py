"""
UnifiedProvider — single entry point that combines bridge_client + orats_provider.

v2.0: Enhanced bridge methods supporting date/source/filtering params.
full_analysis() is fault-tolerant: any sub-query failure does not block others.
Supports context manager protocol.
"""

from __future__ import annotations

import traceback
from typing import Any, Dict, List, Optional

from bridge_client import BridgeClient, BridgeSnapshot, select_micro_template
from orats_provider import OratsClient, OratsConfig
from orats_provider.greeks_exposure import commands as greeks_commands
from orats_provider.volatility import commands as vol_commands


class UnifiedProvider:
    """Unified provider integrating Bridge + ORATS data sources."""

    def __init__(
        self,
        bridge_url: str = "http://localhost:8668",
        orats_config: Optional[OratsConfig] = None,
        use_cache: bool = True,
    ):
        self._bridge = BridgeClient(base_url=bridge_url)
        self._orats = OratsClient(config=orats_config, use_cache=use_cache)

    # ── Context manager ─────────────────────────────────────────────

    def __enter__(self) -> "UnifiedProvider":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._bridge.close()
        self._orats.close()

    # ── Bridge delegates ────────────────────────────────────────────

    def get_bridge_snapshot(
        self,
        symbol: str,
        date: Optional[str] = None,
        source: Optional[str] = None,
    ) -> BridgeSnapshot:
        """Fetch a single bridge snapshot, optionally filtered by date/source."""
        return self._bridge.get_snapshot(symbol, date=date, source=source)

    def get_bridge_batch(
        self,
        symbols: Optional[List[str]] = None,
        source: Optional[str] = None,
        date: Optional[str] = None,
        min_direction_score: Optional[float] = None,
        min_vol_score: Optional[float] = None,
        limit: Optional[int] = None,
        filtering: Optional[Dict[str, Any]] = None,
        sorting: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> List[BridgeSnapshot]:
        """Fetch batch bridge snapshots with full filtering support."""
        return self._bridge.get_batch(
            symbols=symbols,
            source=source,
            date=date,
            min_direction_score=min_direction_score,
            min_vol_score=min_vol_score,
            limit=limit,
            filtering=filtering,
            sorting=sorting,
        )

    def get_micro_template(self, symbol: str) -> Dict[str, Any]:
        snap = self._bridge.get_snapshot(symbol)
        template = select_micro_template(snap)
        return {"symbol": symbol, "micro_template": template, "snapshot": snap.to_dict()}

    # ── Greeks delegates ────────────────────────────────────────────

    def greeks(self, symbol: str, command: str, **kwargs: Any) -> Dict[str, Any]:
        result = greeks_commands.execute(self._orats, symbol, command, **kwargs)
        return result.to_dict()

    # ── Volatility delegates ────────────────────────────────────────

    def volatility(self, symbol: str, command: str, **kwargs: Any) -> Dict[str, Any]:
        result = vol_commands.execute(self._orats, symbol, command, **kwargs)
        return result.to_dict()

    # ── Full analysis (fault-tolerant) ──────────────────────────────

    def full_analysis(
        self,
        symbol: str,
        greeks_commands_list: Optional[List[str]] = None,
        vol_commands_list: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        if greeks_commands_list is None:
            greeks_commands_list = ["gex", "dex", "vex", "vanna"]
        if vol_commands_list is None:
            vol_commands_list = ["skew", "term", "surface"]

        result: Dict[str, Any] = {
            "symbol": symbol,
            "bridge": None,
            "micro_template": None,
            "greeks": {},
            "volatility": {},
            "errors": [],
        }

        try:
            snap = self._bridge.get_snapshot(symbol)
            result["bridge"] = snap.to_dict()
            result["micro_template"] = select_micro_template(snap)
        except Exception as e:
            result["errors"].append({"source": "bridge", "error": str(e)})

        for cmd in greeks_commands_list:
            try:
                r = greeks_commands.execute(self._orats, symbol, cmd, **kwargs)
                result["greeks"][cmd] = r.to_dict()
            except Exception as e:
                result["errors"].append({"source": f"greeks.{cmd}", "error": str(e)})

        for cmd in vol_commands_list:
            try:
                r = vol_commands.execute(self._orats, symbol, cmd, **kwargs)
                result["volatility"][cmd] = r.to_dict()
            except Exception as e:
                result["errors"].append({"source": f"volatility.{cmd}", "error": str(e)})

        return result
