from __future__ import annotations

from typing import Any

from app.multibot.runtime import _latest_ob, _m5_confirmed, _stable_ob_key, _trend


def decide(conn, bot: dict[str, Any], tick: dict[str, Any], params: dict[str, Any], now: int) -> dict[str, Any] | None:
    """Trend-following + Order Block retest strategy.

    Returns a decision dict with keys: action, entry, stop_loss, take_profit, ob_key.
    Returns None to HOLD (no action).
    """
    bid = float(tick["bid"])
    ask = float(tick["ask"])
    mid = (bid + ask) / 2
    trend = _trend(bot["symbol"], bot["timeframe"])
    if trend == "WARMING_UP":
        return None

    ob = _latest_ob(
        bot["symbol"],
        bot["timeframe"],
        int(params["ob_strong_score"]),
        bool(params.get("allow_tested_once", True)),
    )
    if not ob:
        return None

    side = str(ob["side"]).lower()
    if (side == "bullish" and trend != "BULLISH") or (side == "bearish" and trend != "BEARISH"):
        return None
    if params.get("require_m5_confirmation") and not _m5_confirmed(bot["symbol"], side):
        return None

    low, high = float(ob["ob_low"]), float(ob["ob_high"])
    if not (low <= mid <= high):
        return None

    ob_key = _stable_ob_key(ob)
    entry = (low + high) / 2
    ob_range = high - low
    buffer = ob_range * float(params["sl_buffer_ratio"])

    if side == "bullish":
        sl = low - buffer
        risk_distance = entry - sl
        tp = entry + float(params["tp_r_multiple"]) * risk_distance
        action = "buy"
    else:
        sl = high + buffer
        risk_distance = sl - entry
        tp = entry - float(params["tp_r_multiple"]) * risk_distance
        action = "sell"

    if risk_distance <= 0:
        return None
    rr = abs(tp - entry) / risk_distance
    if rr < 1.5:
        return None

    return {
        "action": action,
        "entry": entry,
        "stop_loss": sl,
        "take_profit": tp,
        "ob_key": ob_key,
        "risk_reward": rr,
    }
