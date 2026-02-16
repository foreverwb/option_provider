"""Volatility analysis sub-package: analyzer, commands, formatter."""

from .analyzer import (
    compute_skew_by_expiry, compute_smile,
    compute_term_structure_by_expiry, compute_constant_maturity_iv,
    detect_contango_state, compute_vol_surface,
)
from .commands import execute, execute_from_records, COMMANDS
from .formatter import to_json, to_summary, to_chart_data

__all__ = [
    "compute_skew_by_expiry", "compute_smile",
    "compute_term_structure_by_expiry", "compute_constant_maturity_iv",
    "detect_contango_state", "compute_vol_surface",
    "execute", "execute_from_records", "COMMANDS",
    "to_json", "to_summary", "to_chart_data",
]
