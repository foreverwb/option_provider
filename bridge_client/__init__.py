"""
bridge_client — HTTP-based client for the volatility_analysis Bridge API.
Fully decoupled from core modules; communicates via REST only.
"""

from .models import BridgeSnapshot, TermStructureSnapshot
from .client import BridgeClient, AsyncBridgeClient
from .micro_templates import select_micro_template, map_horizon_bias_to_dte_bias

__all__ = [
    "BridgeSnapshot",
    "TermStructureSnapshot",
    "BridgeClient",
    "AsyncBridgeClient",
    "select_micro_template",
    "map_horizon_bias_to_dte_bias",
]
