"""
Pure micro-template selection logic with no core-module dependency.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .models import BridgeSnapshot


def _base_template_from_quadrant(quadrant: str) -> str:
    mapping = {
        "偏多—买波": "bull_long_vol",
        "偏多—卖波": "bull_short_vol",
        "偏空—买波": "bear_long_vol",
        "偏空—卖波": "bear_short_vol",
        "中性/待观察": "neutral_watch",
    }
    return mapping.get(quadrant, "generic_micro")


def map_horizon_bias_to_dte_bias(horizon_bias: Any, cfg: Dict[str, Any] | None = None) -> str:
    cfg = cfg or {}
    default_map = {
        "short": "short_term_0_30d",
        "mid": "mid_term_30_60d",
        "long": "long_term_60d_plus",
        "neutral": "neutral",
    }
    custom_map = cfg.get("term_structure_dte_bias_map")
    mapping = default_map
    if isinstance(custom_map, dict):
        mapping = {
            "short": str(custom_map.get("short", default_map["short"])),
            "mid": str(custom_map.get("mid", default_map["mid"])),
            "long": str(custom_map.get("long", default_map["long"])),
            "neutral": str(custom_map.get("neutral", default_map["neutral"])),
        }

    hb = str(horizon_bias or "neutral").lower()
    if hb not in {"short", "mid", "long", "neutral"}:
        hb = "neutral"
    return mapping[hb]


def _resolve_term_structure_profile(snapshot: BridgeSnapshot, cfg: Dict[str, Any]) -> Dict[str, str]:
    ts = snapshot.term_structure
    if ts and isinstance(ts.label_code, str) and isinstance(ts.horizon_bias, str):
        hb = ts.horizon_bias.lower()
        if hb not in {"short", "mid", "long", "neutral"}:
            hb = "neutral"
        return {
            "label_code": ts.label_code,
            "horizon_bias": hb,
            "dte_bias": map_horizon_bias_to_dte_bias(hb, cfg),
        }

    return {
        "label_code": "unknown",
        "horizon_bias": "neutral",
        "dte_bias": map_horizon_bias_to_dte_bias("neutral", cfg),
    }


def select_micro_template(
    snapshot: BridgeSnapshot,
    cfg: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Select a micro template from a BridgeSnapshot.
    """
    cfg = cfg or {}
    if not isinstance(snapshot, BridgeSnapshot):
        snapshot = BridgeSnapshot.from_dict(snapshot if isinstance(snapshot, dict) else {})

    exec_state = snapshot.execution_state
    quadrant = exec_state.get("quadrant")
    template = _base_template_from_quadrant(quadrant)

    overlays_hit: List[str] = []
    disable_conditions_hit: List[str] = []
    risk_overlays: List[str] = []

    permission = exec_state.get("trade_permission", "NORMAL")
    reasons = list(exec_state.get("permission_reasons") or [])
    disabled = set(exec_state.get("disabled_structures") or [])
    posture = exec_state.get("posture_5d")
    term_profile = _resolve_term_structure_profile(snapshot, cfg)

    severity = {"NORMAL": 0, "ALLOW_DEFINED_RISK_ONLY": 1, "NO_TRADE": 2}

    def elevate(target: str, code: str, add_disabled: bool = False) -> None:
        nonlocal permission
        if severity.get(target, 0) > severity.get(permission, 0):
            permission = target
        reasons.append(code)
        if add_disabled:
            disabled.update(
                {
                    "naked_short_put",
                    "naked_short_call",
                    "short_strangle",
                    "short_call_ratio",
                    "short_put_ratio",
                }
            )

    dte_bias = term_profile["dte_bias"]
    if term_profile["label_code"] != "unknown":
        overlays_hit.append(f"term_structure_{term_profile['label_code']}")

    if posture == "TREND_CONFIRM":
        overlays_hit.append("posture_trend_confirm")
        if dte_bias == "neutral":
            dte_bias = "mid_term_30_60d"
        risk_overlays.append("顺势确认：保持系统化执行，关注时间止盈")
    elif posture == "COUNTERTREND":
        overlays_hit.append("posture_countertrend")
        elevate("ALLOW_DEFINED_RISK_ONLY", "POSTURE_COUNTERTREND_OVERLAY", add_disabled=True)
        if dte_bias == "neutral":
            dte_bias = "short_term_0_30d"
        disable_conditions_hit.append("posture_countertrend_defined_risk")
        risk_overlays.append("逆势尝试：仅定义风险，小仓位，等待确认")
    elif posture == "ONE_DAY_SHOCK":
        overlays_hit.append("posture_one_day_shock")
        elevate("ALLOW_DEFINED_RISK_ONLY", "POSTURE_ONE_DAY_SHOCK_OVERLAY", add_disabled=True)
        if dte_bias == "neutral":
            dte_bias = "short_term_0_30d"
        disable_conditions_hit.append("posture_one_day_shock_tail_guard")
        risk_overlays.append("单日冲击：避免裸露尾部/近翼，提示易反复")
    elif posture == "CHOP":
        overlays_hit.append("posture_chop")
        elevate("NO_TRADE", "POSTURE_CHOP_OVERLAY", add_disabled=True)
        dte_bias = "wait_and_see"
        disable_conditions_hit.append("posture_chop_watchlist")
        risk_overlays.append("震荡/混沌：默认观望，等待方向或期限结构改善")

    return {
        "template": template,
        "dte_bias": dte_bias,
        "risk_overlays": risk_overlays,
        "overlays_hit": overlays_hit,
        "disable_conditions_hit": disable_conditions_hit,
        "trade_permission": permission,
        "permission_reasons": reasons,
        "disabled_structures": sorted(disabled),
        "term_structure_label_code": term_profile["label_code"],
        "term_structure_horizon_bias": term_profile["horizon_bias"],
    }
