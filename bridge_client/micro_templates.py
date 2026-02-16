"""
Micro-template selection logic — fully decoupled from core.term_structure.

select_micro_template() takes a BridgeSnapshot and returns the micro-template
code string.  All term-structure helpers (label resolution, horizon-bias → DTE
bias mapping) are reimplemented locally so there is zero import from core.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from .models import BridgeSnapshot, TermStructureSnapshot

# ── Label / bias constants ──────────────────────────────────────────────

TERM_STRUCTURE_LABELS = {
    "STEEP_CONTANGO": "SC",
    "CONTANGO": "C",
    "FLAT": "F",
    "BACKWARDATION": "B",
    "STEEP_BACKWARDATION": "SB",
}

HORIZON_BIAS_MAP = {
    "FRONT_HEAVY": "SHORT",
    "BALANCED": "MID",
    "BACK_HEAVY": "LONG",
    "NEUTRAL": "MID",
}

# ── Posture codes ───────────────────────────────────────────────────────

DIRECTION_POSTURE = {
    (-100, -60): "STRONG_BEAR",
    (-60, -20): "BEAR",
    (-20, 20): "NEUTRAL",
    (20, 60): "BULL",
    (60, 100): "STRONG_BULL",
}

VOLATILITY_POSTURE = {
    (-100, -60): "VOL_CRUSH",
    (-60, -20): "LOW_VOL",
    (-20, 20): "NORMAL_VOL",
    (20, 60): "HIGH_VOL",
    (60, 100): "VOL_SPIKE",
}

# ── Micro-template mapping ─────────────────────────────────────────────

# Primary key:  (direction_posture, volatility_posture)
# Value:        base template code
_TEMPLATE_MAP: Dict[Tuple[str, str], str] = {
    # Strong bullish
    ("STRONG_BULL", "VOL_CRUSH"): "BULL_DEBIT_SPREAD",
    ("STRONG_BULL", "LOW_VOL"): "BULL_DEBIT_SPREAD",
    ("STRONG_BULL", "NORMAL_VOL"): "LONG_CALL",
    ("STRONG_BULL", "HIGH_VOL"): "BULL_PUT_SPREAD",
    ("STRONG_BULL", "VOL_SPIKE"): "BULL_PUT_SPREAD",
    # Bullish
    ("BULL", "VOL_CRUSH"): "BULL_CALL_SPREAD",
    ("BULL", "LOW_VOL"): "BULL_CALL_SPREAD",
    ("BULL", "NORMAL_VOL"): "BULL_CALL_SPREAD",
    ("BULL", "HIGH_VOL"): "BULL_PUT_SPREAD",
    ("BULL", "VOL_SPIKE"): "SHORT_PUT",
    # Neutral
    ("NEUTRAL", "VOL_CRUSH"): "LONG_STRADDLE",
    ("NEUTRAL", "LOW_VOL"): "LONG_STRANGLE",
    ("NEUTRAL", "NORMAL_VOL"): "IRON_CONDOR",
    ("NEUTRAL", "HIGH_VOL"): "SHORT_STRANGLE",
    ("NEUTRAL", "VOL_SPIKE"): "SHORT_STRADDLE",
    # Bearish
    ("BEAR", "VOL_CRUSH"): "BEAR_PUT_SPREAD",
    ("BEAR", "LOW_VOL"): "BEAR_PUT_SPREAD",
    ("BEAR", "NORMAL_VOL"): "BEAR_PUT_SPREAD",
    ("BEAR", "HIGH_VOL"): "BEAR_CALL_SPREAD",
    ("BEAR", "VOL_SPIKE"): "SHORT_CALL",
    # Strong bearish
    ("STRONG_BEAR", "VOL_CRUSH"): "BEAR_DEBIT_SPREAD",
    ("STRONG_BEAR", "LOW_VOL"): "BEAR_DEBIT_SPREAD",
    ("STRONG_BEAR", "NORMAL_VOL"): "LONG_PUT",
    ("STRONG_BEAR", "HIGH_VOL"): "BEAR_CALL_SPREAD",
    ("STRONG_BEAR", "VOL_SPIKE"): "BEAR_CALL_SPREAD",
}

_DEFAULT_TEMPLATE = "IRON_CONDOR"


# ── Internal helpers ────────────────────────────────────────────────────

def _score_to_posture(score: float, mapping: Dict[Tuple[int, int], str]) -> str:
    """Map a -100..+100 score to a posture label using range buckets."""
    for (lo, hi), label in mapping.items():
        if lo <= score < hi:
            return label
    # Edge: score == 100
    if score >= 60:
        return list(mapping.values())[-1]
    return "NEUTRAL"


def _resolve_term_structure_profile(
    snapshot: BridgeSnapshot,
) -> Tuple[str, str]:
    """
    Extract (label_code, horizon_bias) from a BridgeSnapshot.
    Reads from snapshot.term_structure first; falls back to
    snapshot.market_state flat fields for backward compat.
    """
    ts = snapshot.term_structure
    if ts is not None and isinstance(ts, TermStructureSnapshot):
        label_code = ts.label_code or "FLAT"
        horizon_bias = ts.horizon_bias or "NEUTRAL"
        return label_code, horizon_bias

    # Fallback: market_state flat structure
    ms = snapshot.market_state or {}
    label_code = ms.get("label_code", ms.get("term_structure_label", "FLAT"))
    horizon_bias = ms.get("horizon_bias", "NEUTRAL")
    return label_code, horizon_bias


def map_horizon_bias_to_dte_bias(horizon_bias: str) -> str:
    """
    Convert a horizon_bias string to DTE-bias category.
    Re-implemented locally (was core.term_structure.map_horizon_bias_to_dte_bias).
    """
    return HORIZON_BIAS_MAP.get(horizon_bias, "MID")


def _apply_earnings_overlay(template: str, snapshot: BridgeSnapshot) -> str:
    """If earnings are imminent, nudge toward vol-selling or neutral templates."""
    if snapshot.earnings_proximity in ("IMMINENT", "THIS_WEEK"):
        # Near earnings → prefer defined-risk / neutral
        if "LONG" in template and "SPREAD" not in template:
            return template.replace("LONG", "BULL" if "CALL" in template else "BEAR") + "_SPREAD"
    return template


def _apply_term_structure_overlay(
    template: str,
    label_code: str,
    dte_bias: str,
) -> str:
    """
    Adjust template suffix based on term-structure regime.
    Steep backwardation → prefer shorter DTE (front-month).
    Steep contango → prefer longer DTE.
    """
    suffix = ""
    if label_code in ("SB", "STEEP_BACKWARDATION"):
        suffix = "_FRONT"
    elif label_code in ("SC", "STEEP_CONTANGO"):
        suffix = "_BACK"

    # DTE bias override
    if dte_bias == "SHORT":
        suffix = "_FRONT"
    elif dte_bias == "LONG":
        suffix = "_BACK"

    # Don't double-add
    if suffix and not template.endswith(suffix):
        return template + suffix
    return template


# ── Public API ──────────────────────────────────────────────────────────

def select_micro_template(snapshot: BridgeSnapshot) -> str:
    """
    Select the optimal micro-template code for a given BridgeSnapshot.

    Steps:
      1. Map direction_score → direction posture
      2. Map volatility_score → volatility posture
      3. Look up base template from (direction, vol) grid
      4. Apply earnings overlay
      5. Apply term-structure overlay (label + DTE bias)

    Returns the final micro-template code string.
    """
    dir_posture = _score_to_posture(snapshot.direction_score, DIRECTION_POSTURE)
    vol_posture = _score_to_posture(snapshot.volatility_score, VOLATILITY_POSTURE)

    base = _TEMPLATE_MAP.get((dir_posture, vol_posture), _DEFAULT_TEMPLATE)

    # Earnings overlay
    base = _apply_earnings_overlay(base, snapshot)

    # Term structure overlay
    label_code, horizon_bias = _resolve_term_structure_profile(snapshot)
    dte_bias = map_horizon_bias_to_dte_bias(horizon_bias)
    result = _apply_term_structure_overlay(base, label_code, dte_bias)

    return result
