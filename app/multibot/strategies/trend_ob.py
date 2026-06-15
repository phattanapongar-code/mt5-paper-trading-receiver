from __future__ import annotations

from typing import Any

from app import storage
from app.multibot.runtime import _latest_ob, _m5_confirmed, _stable_ob_key, _trend

TIMEFRAMES: dict[str, int] = {"M1": 60, "M5": 300, "M15": 900, "H1": 3600}


def _ob_age_in_candles(symbol: str, timeframe: str, break_open_time: int) -> int | None:
    """Return how many candles have passed since this OB's break_open_time."""
    seconds = TIMEFRAMES.get(timeframe)
    if not seconds:
        return None
    latest = storage.query_one(
        "SELECT open_time FROM candles WHERE symbol=? AND timeframe=? AND is_closed=1 ORDER BY open_time DESC LIMIT 1",
        (symbol, timeframe),
    )
    if not latest:
        return None
    return int((int(latest["open_time"]) - break_open_time) // seconds)


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

    # OB freshness filter: skip OBs older than max_age candles
    max_age = int(params.get("ob_max_age_candles", 20))
    ob_age = _ob_age_in_candles(bot["symbol"], bot["timeframe"], int(ob["break_open_time"]))
    if ob_age is not None and ob_age > max_age:
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
    # Entry at the OB boundary closest to current price for better fill probability
    entry = high if side == "bullish" else low
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
