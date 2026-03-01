"""
Micro boundary computation engine.

Reads a bridge snapshot dict + centralized rules (boundary_rules.yaml)
and outputs a fully-populated MicroBoundary dataclass.

Design invariants
-----------------
* No sub-function raises — missing data ➜ fallback value + entry in *warnings*.
* Module-level ``_DEFAULT_RULES`` used when YAML load fails.
* ``safe_float`` reused from ``bridge_provider``.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .bridge_builder import safe_float
from .models import (
    BaseBoundary,
    BoundaryMetadata,
    ConfidenceBoundary,
    Degradation,
    DirectionalRange,
    LiquidityBoundary,
    MicroBoundary,
    OIAvailability,
    StrategyOverlay,
    SwingOverlay,
    TemporalBoundary,
    TermStructureBoundary,
    VolQuantOverlay,
    VolRange,
)

logger = logging.getLogger(__name__)

# ======================================================================
# Default rules (fallback when YAML is unavailable)
# ======================================================================

_DEFAULT_RULES: Dict[str, Any] = {
    "version": "1.0",
    "liquidity": {
        "strikes_map": {"excellent": 21, "good": 17, "fair": 13, "poor": 9},
        "default_strikes": 15,
        "poor_blocks_long_vol": True,
    },
    "oi": {"unavailable_max_strikes": 11},
    "confidence": {
        "buy_vol_min": 0.35,
        "sell_vol_min": 0.50,
        "blocked_threshold": 0.20,
        "missing_default": 0.50,
        "low_context": "minimum",
        "blocked_context": "blocked",
        "meso_overrides": {},
    },
    "earnings": {
        "enabled": True,
        "window_days": 14,
        "event_context": "event",
        "imminent_days": 3,
        "imminent_max_dte": 21,
        "tighten": {"dte_extrinsic_ntm": 30, "dte_theta_atm": 14, "dte_gex_scale": 0.85},
    },
    "term_structure": {
        "horizon_multipliers": {
            "adjustment_weight": 1.0,
            "bias_weight": 1.0,
            "weights": {"gex": 1.0, "skew": 0.8, "vex": 1.0, "term": 1.0},
            "state_overrides": {
                "short_low": {"gex_scale": 0.85, "skew_scale": 0.90, "trigger_scale": 0.85},
                "full_inversion": {"gex_scale": 0.7, "skew_scale": 0.8, "vex_scale": 0.85, "term_scale": 0.85},
                "short_inversion": {"gex_scale": 0.8, "skew_scale": 0.9, "vex_scale": 0.95, "term_scale": 0.95},
                "far_elevated": {"gex_scale": 1.0, "skew_scale": 1.0, "vex_scale": 1.15, "term_scale": 1.15},
            },
        }
    },
    "clamps": {
        "strikes": {"min": 7, "max": 31},
        "dte_short": {"min": 7, "max": 120},
        "dte_mid": {"min": 14, "max": 180},
        "dte_long": {"min": 30, "max": 365},
        "dte_term": {"min": 60, "max": 730},
    },
    "data_quality": {"poor_confidence_penalty": 0.80},
    "degradation": {
        "mode_priority": ["blocked", "fallback", "partial", "full"],
    },
}

# Total expected key fields used for data-completeness calculation.
_EXPECTED_FIELDS = (
    "direction_score", "vol_score", "direction_bias", "vol_bias",
    "confidence", "liquidity", "oi_data_available", "data_quality",
    "trade_permission", "fear_regime",
)


# ======================================================================
# Rule loader
# ======================================================================

def load_boundary_rules(path: Optional[str] = None) -> Dict[str, Any]:
    """Load centralized rules YAML.  Falls back to ``_DEFAULT_RULES``."""
    if path is None:
        # Try the canonical location relative to *this* file.
        path = str(Path(__file__).with_name("boundary_rules.yaml"))

    try:
        with open(path, "r", encoding="utf-8") as fh:
            rules = yaml.safe_load(fh)
        if isinstance(rules, dict):
            return rules
    except Exception as exc:  # noqa: BLE001
        logger.warning("boundary_rules.yaml load failed (%s); using built-in defaults", exc)
    return dict(_DEFAULT_RULES)


# ======================================================================
# Helper — safe dict access
# ======================================================================

def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return default


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ======================================================================
# Sub-functions
# ======================================================================

def _resolve_meso_state(exec_state: Dict[str, Any]) -> str:
    """Derive meso_state string from execution_state biases."""
    d_bias = _safe_str(exec_state.get("direction_bias"), "中性")
    v_bias = _safe_str(exec_state.get("vol_bias"), "中性")
    return f"{d_bias}-{v_bias}"


# --- 1 ---
def _compute_directional_range(
    exec_state: Dict[str, Any],
    meso_state: str,
) -> DirectionalRange:
    d_score = safe_float(exec_state.get("direction_score"), 0.0)
    d_bias = _safe_str(exec_state.get("direction_bias"))

    # upper/lower: the raw score provides the magnitude,
    # bias tells us which side to anchor.
    if d_bias == "偏多":
        upper = abs(d_score)
        lower = -abs(d_score) * 0.3
        bias = "bullish"
    elif d_bias == "偏空":
        upper = abs(d_score) * 0.3
        lower = -abs(d_score)
        bias = "bearish"
    else:
        upper = abs(d_score) * 0.5
        lower = -abs(d_score) * 0.5
        bias = "neutral"

    return DirectionalRange(
        upper=round(upper, 4),
        lower=round(lower, 4),
        bias=bias,
        direction_score=d_score,
        direction_bias=d_bias,
    )


# --- 2 ---
def _compute_vol_range(
    market_state: Dict[str, Any],
    exec_state: Dict[str, Any],
    meso_state: str,
) -> VolRange:
    iv30 = safe_float(market_state.get("iv30"), 0.0)
    hv20 = safe_float(market_state.get("hv20"), 0.0)
    ivr = safe_float(market_state.get("ivr") or exec_state.get("ivr"), 0.0)
    vol_score = safe_float(exec_state.get("vol_score"), 0.0)
    vol_bias = _safe_str(exec_state.get("vol_bias"))

    # VRP = iv30 / hv20 (ratio); handle zero
    vrp = round(iv30 / hv20, 4) if hv20 > 0 else 0.0

    if vrp > 1.10:
        vrp_regime = "EXPANDING"
    elif vrp < 0.90:
        vrp_regime = "COMPRESSING"
    else:
        vrp_regime = "STABLE"

    # IV range — simple heuristic from ivr
    iv_low = round(iv30 * max(1.0 - ivr / 100.0, 0.5), 4) if iv30 else None
    iv_high = round(iv30 * min(1.0 + (100.0 - ivr) / 100.0, 2.0), 4) if iv30 else None

    return VolRange(
        iv_current=iv30 or None,
        iv_low=iv_low,
        iv_high=iv_high,
        rv_ref=hv20 or None,
        vrp=vrp,
        vrp_regime=vrp_regime,
        ivr=ivr or None,
        vol_score=vol_score,
        vol_bias=vol_bias or None,
    )


# --- 3 ---
def _compute_liquidity(
    exec_state: Dict[str, Any],
    rules: Dict[str, Any],
    meso_state: str,
) -> Tuple[LiquidityBoundary, List[str]]:
    liq_rules = _as_dict(rules.get("liquidity"))
    strikes_map = _as_dict(liq_rules.get("strikes_map"))
    default_strikes = int(liq_rules.get("default_strikes", 15))
    poor_blocks = bool(liq_rules.get("poor_blocks_long_vol", True))

    fallback: List[str] = []

    raw_label = exec_state.get("liquidity")
    if not isinstance(raw_label, str) or raw_label not in strikes_map:
        fallback.append("liquidity_label_missing→default_strikes")
        raw_label = raw_label if isinstance(raw_label, str) else None
        strikes_ceiling = default_strikes
        tier = "unknown"
    else:
        strikes_ceiling = int(strikes_map.get(raw_label, default_strikes))
        tier = raw_label

    score = safe_float(exec_state.get("active_open_ratio"), 0.0)

    # poor + 买波 → insufficient
    is_buy_vol = "买波" in meso_state
    is_poor = tier == "poor"
    is_sufficient = not (is_poor and is_buy_vol and poor_blocks)

    return LiquidityBoundary(
        raw_label=raw_label,
        score=score or None,
        tier=tier,
        is_sufficient=is_sufficient,
        strikes_ceiling=strikes_ceiling,
        active_open_ratio=safe_float(exec_state.get("active_open_ratio")),
    ), fallback


# --- 4 ---
def _compute_oi(
    exec_state: Dict[str, Any],
    rules: Dict[str, Any],
) -> Tuple[OIAvailability, List[str]]:
    oi_rules = _as_dict(rules.get("oi"))
    unavail_max = int(oi_rules.get("unavailable_max_strikes", 11))

    fallback: List[str] = []
    available = exec_state.get("oi_data_available")

    if available is None:
        fallback.append("oi_data_available_missing→assume_unavailable")
        available = False

    strikes_cap: Optional[int] = None
    if not available:
        strikes_cap = unavail_max

    return OIAvailability(
        available=bool(available),
        strikes_cap=strikes_cap,
        concentration={},
    ), fallback


# --- 5 ---
def _compute_confidence(
    exec_state: Dict[str, Any],
    rules: Dict[str, Any],
    meso_state: str,
) -> Tuple[ConfidenceBoundary, List[str]]:
    conf_rules = _as_dict(rules.get("confidence"))
    dq_rules = _as_dict(rules.get("data_quality"))

    blocked_threshold = float(conf_rules.get("blocked_threshold", 0.20))
    missing_default = float(conf_rules.get("missing_default", 0.50))
    low_context = str(conf_rules.get("low_context", "minimum"))
    blocked_context = str(conf_rules.get("blocked_context", "blocked"))

    fallback: List[str] = []

    # Determine per-meso threshold
    meso_overrides = _as_dict(conf_rules.get("meso_overrides"))
    if meso_state in meso_overrides:
        threshold = float(_as_dict(meso_overrides[meso_state]).get("min", conf_rules.get("buy_vol_min", 0.35)))
    elif "买波" in meso_state:
        threshold = float(conf_rules.get("buy_vol_min", 0.35))
    else:
        threshold = float(conf_rules.get("sell_vol_min", 0.50))

    raw_conf = exec_state.get("confidence")
    if raw_conf is None:
        fallback.append("confidence_missing→default")
        level = missing_default
    else:
        level = safe_float(raw_conf, missing_default)

    # Data quality penalty
    data_quality = _safe_str(exec_state.get("data_quality"), "ok").lower()
    if data_quality == "poor":
        penalty = float(dq_rules.get("poor_confidence_penalty", 0.80))
        level = level * penalty
        fallback.append("data_quality_poor→confidence_penalized")

    # Gate logic
    if level < blocked_threshold:
        gate_passed = False
        recommended_context = blocked_context
    elif level < threshold:
        gate_passed = False
        recommended_context = low_context
    else:
        gate_passed = True
        recommended_context = "standard"

    notes = exec_state.get("confidence_notes")

    return ConfidenceBoundary(
        level=round(level, 4),
        gate_passed=gate_passed,
        gate_threshold=threshold,
        recommended_context=recommended_context,
        notes=_safe_str(notes) if notes else None,
    ), fallback


# --- 6 ---
def _compute_temporal(
    event_state: Dict[str, Any],
    rules: Dict[str, Any],
) -> Tuple[TemporalBoundary, List[str]]:
    earn_rules = _as_dict(rules.get("earnings"))
    fallback: List[str] = []

    earnings_date = event_state.get("earnings_date")
    days_raw = event_state.get("days_to_earnings")
    is_index = _safe_bool(event_state.get("is_index"))
    is_squeeze = _safe_bool(event_state.get("is_squeeze"))

    window_days = int(earn_rules.get("window_days", 14))
    imminent_days = int(earn_rules.get("imminent_days", 3))
    enabled = bool(earn_rules.get("enabled", True))

    if days_raw is not None:
        try:
            days = int(days_raw)
        except (TypeError, ValueError):
            days = None
            fallback.append("days_to_earnings_parse_failed")
    else:
        days = None

    earnings_window = False
    dte_cluster = "standard"

    if enabled and days is not None:
        if 0 <= days <= window_days:
            earnings_window = True
            if days <= imminent_days:
                dte_cluster = "event_imminent"
            else:
                dte_cluster = "event_short"

    return TemporalBoundary(
        earnings_window=earnings_window,
        days_to_earnings=days,
        earnings_date=_safe_str(earnings_date) if earnings_date else None,
        dte_cluster=dte_cluster,
        is_index=is_index,
        is_squeeze=is_squeeze,
    ), fallback


# --- 7 ---
def _compute_term_structure(
    term_data: Dict[str, Any],
    rules: Dict[str, Any],
) -> TermStructureBoundary:
    """
    Compute term structure boundary with scale_factors.

    Scale-factor logic is aligned with gexbot_param_resolver.py L176-204:
    1. Start with base weights (gex=1.0, skew=0.8, vex=1.0, term=1.0).
    2. For each active state_flag, look up state_overrides and multiply
       the corresponding dimension scale.
    3. Resulting scale_factors dict → consumed downstream.
    """
    ts_rules = _as_dict(rules.get("term_structure"))
    hm = _as_dict(ts_rules.get("horizon_multipliers"))
    base_weights = _as_dict(hm.get("weights"))
    state_overrides = _as_dict(hm.get("state_overrides"))

    label_code = _safe_str(term_data.get("label_code"))
    adjustment = safe_float(term_data.get("adjustment"), 0.0)
    horizon_bias = _as_dict(term_data.get("horizon_bias"))
    state_flags = _as_dict(term_data.get("state_flags"))

    # --- Compute scale_factors (aligned w/ gexbot_param_resolver) ---
    # Start from base weights as dimension scales
    scale_factors: Dict[str, float] = {
        "gex_scale": float(base_weights.get("gex", 1.0)),
        "skew_scale": float(base_weights.get("skew", 0.8)),
        "vex_scale": float(base_weights.get("vex", 1.0)),
        "term_scale": float(base_weights.get("term", 1.0)),
        "trigger_scale": 1.0,
    }

    # Apply state_overrides for each active flag
    for flag_name, flag_value in state_flags.items():
        if not flag_value:
            continue
        overrides = _as_dict(state_overrides.get(flag_name))
        for dim, dim_val in overrides.items():
            if dim in scale_factors:
                scale_factors[dim] = round(scale_factors[dim] * safe_float(dim_val, 1.0), 4)

    return TermStructureBoundary(
        label_code=label_code or None,
        adjustment=round(adjustment, 4),
        horizon_bias=horizon_bias,
        state_flags={k: bool(v) for k, v in state_flags.items()},
        scale_factors=scale_factors,
    )


# --- 8 ---
def _compute_effective_strikes(
    liquidity: LiquidityBoundary,
    oi: OIAvailability,
    rules: Dict[str, Any],
) -> int:
    clamps = _as_dict(_as_dict(rules.get("clamps")).get("strikes"))
    lo = int(clamps.get("min", 7))
    hi = int(clamps.get("max", 31))

    liq_ceil = liquidity.strikes_ceiling if liquidity.strikes_ceiling is not None else hi
    oi_cap = oi.strikes_cap if oi.strikes_cap is not None else hi

    effective = min(liq_ceil, oi_cap, hi)
    return int(_clamp(effective, lo, hi))


# --- 9 ---
def _compute_effective_context(
    confidence: ConfidenceBoundary,
    temporal: TemporalBoundary,
    exec_state: Dict[str, Any],
) -> str:
    """
    Priority: blocked > event > minimum > standard.
    trade_permission != "允许" → blocked
    """
    permission = _safe_str(exec_state.get("trade_permission"), "允许")

    if permission not in ("允许", ""):
        return "blocked"

    conf_ctx = confidence.recommended_context or "standard"

    if conf_ctx == "blocked":
        return "blocked"

    if temporal.earnings_window:
        # Earnings overrides to "event" unless blocked
        if conf_ctx == "minimum":
            return "event"  # event takes precedence over minimum
        return "event"

    return conf_ctx


# --- 10 ---
def _compute_swing_overlay(
    market_state: Dict[str, Any],
    base: BaseBoundary,
    meso_state: str,
) -> SwingOverlay:
    """Derive swing scenario from market params (aligned w/ pre_calculator)."""
    vix = safe_float(market_state.get("vix"), 18.0)
    ivr = safe_float(market_state.get("ivr"), 50.0)
    iv30 = safe_float(market_state.get("iv30"), 0.0)
    hv20 = safe_float(market_state.get("hv20"), 0.0)

    # Scenario logic aligned w/ pre_calculator.py L43-103
    if vix > 30:
        scenario = "high_vix"
    elif vix > 22:
        scenario = "elevated_vix"
    elif ivr > 70:
        scenario = "high_ivr"
    elif ivr < 20:
        scenario = "low_ivr"
    else:
        scenario = "normal"

    params: Dict[str, Any] = {"vix": vix, "ivr": ivr}

    if scenario == "high_vix":
        params["wing_width_adj"] = 1.3
        params["dte_preference"] = "short"
    elif scenario == "elevated_vix":
        params["wing_width_adj"] = 1.15
        params["dte_preference"] = "mid"
    elif scenario == "high_ivr":
        params["wing_width_adj"] = 1.1
        params["dte_preference"] = "mid"
    elif scenario == "low_ivr":
        params["wing_width_adj"] = 0.85
        params["dte_preference"] = "long"
    else:
        params["wing_width_adj"] = 1.0
        params["dte_preference"] = "mid"

    return SwingOverlay(scenario=scenario, suggested_dyn_params=params)


# --- 11 ---
def _compute_vol_quant_overlay(
    base: BaseBoundary,
    term_structure: TermStructureBoundary,
    effective_context: str,
    rules: Dict[str, Any],
) -> VolQuantOverlay:
    return VolQuantOverlay(
        gexbot_context=effective_context,
        horizon_scales=dict(term_structure.scale_factors) if term_structure.scale_factors else {},
    )


# --- 12 ---
def _compute_degradation(
    missing_fields: List[str],
    fallback_rules: List[str],
    warnings: List[str],
    liquidity: LiquidityBoundary,
    confidence: ConfidenceBoundary,
    meso_state: str,
    oi_available: bool = True,
) -> Degradation:
    """
    Determine degradation mode.
    Priority: blocked > fallback > partial > full.
    """
    # Blocked conditions
    is_blocked = False
    if confidence.recommended_context == "blocked":
        is_blocked = True
    if not liquidity.is_sufficient:
        is_blocked = True

    # OI unavailable is a data-quality signal → at least partial
    has_data_gap = (not oi_available) or len(fallback_rules) >= 1

    if is_blocked:
        mode = "blocked"
    elif len(missing_fields) >= 3:
        mode = "fallback"
    elif len(missing_fields) >= 1 or has_data_gap:
        mode = "partial"
    else:
        mode = "full"

    return Degradation(
        mode=mode,
        missing_fields=list(missing_fields),
        fallback_rules_applied=list(fallback_rules),
        warnings=list(warnings),
    )


# --- 13 ---
def _compute_metadata(
    bridge_data: Dict[str, Any],
    rules: Dict[str, Any],
    missing_fields: List[str],
) -> BoundaryMetadata:
    total = len(_EXPECTED_FIELDS)
    present = total - len(missing_fields)
    completeness = round(present / total, 4) if total else 1.0

    timestamp = bridge_data.get("as_of") or bridge_data.get("timestamp")

    return BoundaryMetadata(
        data_completeness=completeness,
        source_freshness=_safe_str(timestamp) if timestamp else None,
        boundary_version=str(rules.get("version", "1.0")),
        rules_source="boundary_rules.yaml",
    )


# ======================================================================
# Internal: detect missing fields
# ======================================================================

def _find_missing_fields(exec_state: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    for f in _EXPECTED_FIELDS:
        if exec_state.get(f) is None:
            missing.append(f)
    return missing


# ======================================================================
# Public entry point
# ======================================================================

def compute_micro_boundary(
    bridge_data: Optional[Dict[str, Any]],
    rules: Optional[Dict[str, Any]] = None,
) -> MicroBoundary:
    """
    Main entry: compute a MicroBoundary from *bridge_data*.

    Args:
        bridge_data: complete bridge snapshot dict
                     (market_state, event_state, execution_state, term_structure).
        rules: optional pre-loaded rules dict; ``None`` → auto-load YAML.

    Returns:
        Fully populated MicroBoundary (never raises).
    """
    if bridge_data is None:
        bridge_data = {}
    if rules is None:
        rules = load_boundary_rules()

    exec_state = _as_dict(bridge_data.get("execution_state"))
    market_state = _as_dict(bridge_data.get("market_state"))
    event_state = _as_dict(bridge_data.get("event_state"))
    term_data = _as_dict(bridge_data.get("term_structure"))

    ticker = _safe_str(bridge_data.get("symbol")) or None
    timestamp = _safe_str(bridge_data.get("as_of")) or None

    # ── 0. missing fields ──
    missing_fields = _find_missing_fields(exec_state)

    all_fallback: List[str] = []
    all_warnings: List[str] = []

    # ── 1. meso_state ──
    meso_state = _resolve_meso_state(exec_state)

    # ── 2-7. sub-boundaries ──
    directional = _compute_directional_range(exec_state, meso_state)
    vol_range = _compute_vol_range(market_state, exec_state, meso_state)

    liquidity, fb = _compute_liquidity(exec_state, rules, meso_state)
    all_fallback.extend(fb)

    oi, fb = _compute_oi(exec_state, rules)
    all_fallback.extend(fb)

    confidence, fb = _compute_confidence(exec_state, rules, meso_state)
    all_fallback.extend(fb)

    temporal, fb = _compute_temporal(event_state, rules)
    all_fallback.extend(fb)

    term_structure = _compute_term_structure(term_data, rules)

    base_boundary = BaseBoundary(
        directional=directional,
        vol_range=vol_range,
        liquidity=liquidity,
        oi=oi,
        confidence=confidence,
        temporal=temporal,
        term_structure=term_structure,
    )

    # ── 8-9. effective values ──
    effective_strikes = _compute_effective_strikes(liquidity, oi, rules)
    effective_context = _compute_effective_context(confidence, temporal, exec_state)

    # ── 10-11. overlays ──
    swing_overlay = _compute_swing_overlay(market_state, base_boundary, meso_state)
    vq_overlay = _compute_vol_quant_overlay(base_boundary, term_structure, effective_context, rules)
    strategy_overlay = StrategyOverlay(swing=swing_overlay, vol_quant=vq_overlay)

    # ── 12. degradation ──
    degradation = _compute_degradation(
        missing_fields, all_fallback, all_warnings,
        liquidity, confidence, meso_state,
        oi_available=bool(oi.available),
    )

    # ── 13. metadata ──
    metadata = _compute_metadata(bridge_data, rules, missing_fields)

    return MicroBoundary(
        ticker=ticker,
        timestamp=timestamp,
        meso_state=meso_state,
        base_boundary=base_boundary,
        effective_strikes=effective_strikes,
        effective_context=effective_context,
        strategy_overlay=strategy_overlay,
        degradation=degradation,
        metadata=metadata,
    )
