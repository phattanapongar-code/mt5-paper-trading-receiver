from __future__ import annotations

from typing import Any

from app import storage
from app.indicators import compute_indicators


def _candles(symbol: str, timeframe: str) -> list[dict[str, Any]]:
    if not storage.table_exists("candles"):
        return []
    rows = storage.query_all(
        "SELECT open, high, low, close, is_closed FROM candles WHERE symbol=? AND timeframe=? AND is_closed=1 ORDER BY open_time DESC LIMIT 300",
        (symbol, timeframe),
    )
    return list(reversed(rows)) if rows else []


def _find_ob(symbol: str, timeframe: str, side: str) -> dict[str, Any] | None:
    if not storage.table_exists("order_blocks"):
        return None
    db_side = {"buy": "bullish", "sell": "bearish"}.get(side, side)
    return storage.query_one(
        "SELECT * FROM order_blocks WHERE symbol=? AND timeframe=? AND side=? AND is_strong=1 AND score>=6 AND status='active' ORDER BY break_open_time DESC LIMIT 1",
        (symbol, timeframe, db_side),
    )


def decide(conn: Any, bot: dict[str, Any], tick: dict[str, Any], params: dict[str, Any], now: int) -> dict[str, Any] | None:
    """Bollinger Band Breakout strategy.

    BUY when close breaks above upper BB (momentum breakout).
    SELL when close breaks below lower BB.
    Uses ATR for SL/TP sizing.
    """
    candles = _candles(bot["symbol"], bot["timeframe"])
    if len(candles) < 25:
        return None

    ind = compute_indicators(candles)
    bb_upper = ind.get("bb_upper")
    bb_lower = ind.get("bb_lower")
    atr14 = ind.get("atr14")
    if bb_upper is None or bb_lower is None or atr14 is None:
        return None

    last_close = float(candles[-1]["close"])
    prev_close = float(candles[-2]["close"]) if len(candles) > 1 else last_close

    min_rr = float(params.get("min_rr", 1.5))
    tp_r = float(params.get("tp_r_multiple", 2.0))

    buy_breakout = prev_close <= bb_upper and last_close > bb_upper
    sell_breakout = prev_close >= bb_lower and last_close < bb_lower

    if buy_breakout:
        ob = _find_ob(bot["symbol"], bot["timeframe"], "buy")
        if ob:
            entry = (float(ob["ob_low"]) + float(ob["ob_high"])) / 2
            sl = float(ob["ob_low"]) - atr14 * 0.3
            tp = entry + (entry - sl) * tp_r
            rr = (tp - entry) / (entry - sl) if entry != sl else 0
            if rr < min_rr:
                return None
            return {
                "action": "buy", "entry": entry, "stop_loss": sl, "take_profit": tp,
                "ob_key": f"bb_ob:buy:{ob.get('break_open_time','?')}:{ob.get('ob_open_time','?')}",
                "risk_reward": rr,
            }
        mid = (float(tick["bid"]) + float(tick["ask"])) / 2
        sl = mid - atr14 * 1.5
        tp = mid + atr14 * 3.0
        risk = mid - sl
        reward = tp - mid
        if risk <= 0 or reward / risk < min_rr:
            return None
        return {
            "action": "buy", "entry": mid, "stop_loss": sl, "take_profit": tp,
            "ob_key": f"bb_atr:buy:{now}", "risk_reward": reward / risk,
        }

    if sell_breakout:
        ob = _find_ob(bot["symbol"], bot["timeframe"], "sell")
        if ob:
            entry = (float(ob["ob_low"]) + float(ob["ob_high"])) / 2
            sl = float(ob["ob_high"]) + atr14 * 0.3
            tp = entry - (sl - entry) * tp_r
            rr = (entry - tp) / (sl - entry) if sl != entry else 0
            if rr < min_rr:
                return None
            return {
                "action": "sell", "entry": entry, "stop_loss": sl, "take_profit": tp,
                "ob_key": f"bb_ob:sell:{ob.get('break_open_time','?')}:{ob.get('ob_open_time','?')}",
                "risk_reward": rr,
            }
        mid = (float(tick["bid"]) + float(tick["ask"])) / 2
        sl = mid + atr14 * 1.5
        tp = mid - atr14 * 3.0
        risk = sl - mid
        reward = mid - tp
        if risk <= 0 or reward / risk < min_rr:
            return None
        return {
            "action": "sell", "entry": mid, "stop_loss": sl, "take_profit": tp,
            "ob_key": f"bb_atr:sell:{now}", "risk_reward": reward / risk,
        }

    return None
