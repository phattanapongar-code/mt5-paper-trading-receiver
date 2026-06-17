from __future__ import annotations

import math
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


def decide(conn, bot: dict[str, Any], tick: dict[str, Any], params: dict[str, Any], now: int) -> dict[str, Any] | None:
    """RSI Mean Reversion with optional trend filter.

    BUY when RSI exits oversold (< oversold threshold).
    SELL when RSI exits overbought (> overbought threshold).
    Uses OB zones for entry when available, otherwise ATR-based SL/TP.
    """
    candles = _candles(bot["symbol"], bot["timeframe"])
    if len(candles) < 20:
        return None

    ind = compute_indicators(candles)
    rsi14 = ind.get("rsi14")
    atr14 = ind.get("atr14")
    if rsi14 is None or atr14 is None:
        return None

    prev_candles = candles[:-1] if len(candles) > 20 else candles
    prev_ind = compute_indicators(prev_candles)
    prev_rsi = prev_ind.get("rsi14")

    trend = str(ind.get("trend", "NEUTRAL"))
    use_trend_filter = bool(params.get("rsi_trend_filter", True))
    oversold = float(params.get("rsi_oversold", 30.0))
    overbought = float(params.get("rsi_overbought", 70.0))
    sl_atr = float(params.get("sl_atr_multiple", 1.5))
    tp_atr = float(params.get("tp_atr_multiple", 3.0))
    min_rr = float(params.get("min_rr", 1.5))

    bid = float(tick["bid"])
    ask = float(tick["ask"])
    mid = (bid + ask) / 2

    buy_signal = prev_rsi is not None and prev_rsi < oversold and rsi14 >= oversold
    sell_signal = prev_rsi is not None and prev_rsi > overbought and rsi14 <= overbought

    if buy_signal:
        if use_trend_filter and trend not in ("BULLISH", "NEUTRAL"):
            return None
        ob = _find_ob(bot["symbol"], bot["timeframe"], "buy")
        if ob:
            entry = (float(ob["ob_low"]) + float(ob["ob_high"])) / 2
            sl = float(ob["ob_low"]) - atr14 * 0.3
            tp = entry + (entry - sl) * float(params.get("tp_r_multiple", 2.0))
            rr = (tp - entry) / (entry - sl) if entry != sl else 0
            if rr < min_rr:
                return None
            return {
                "action": "buy", "entry": entry, "stop_loss": sl, "take_profit": tp,
                "ob_key": f"rsi_ob:buy:{ob.get('break_open_time','?')}:{ob.get('ob_open_time','?')}",
                "risk_reward": rr,
            }
        # Fallback: ATR-based
        sl = mid - atr14 * sl_atr
        tp = mid + atr14 * tp_atr
        risk = mid - sl
        reward = tp - mid
        if risk <= 0 or reward / risk < min_rr:
            return None
        return {
            "action": "buy", "entry": mid, "stop_loss": sl, "take_profit": tp,
            "ob_key": f"rsi_atr:buy:{now}", "risk_reward": reward / risk,
        }

    if sell_signal:
        if use_trend_filter and trend not in ("BEARISH", "NEUTRAL"):
            return None
        ob = _find_ob(bot["symbol"], bot["timeframe"], "sell")
        if ob:
            entry = (float(ob["ob_low"]) + float(ob["ob_high"])) / 2
            sl = float(ob["ob_high"]) + atr14 * 0.3
            tp = entry - (sl - entry) * float(params.get("tp_r_multiple", 2.0))
            rr = (entry - tp) / (sl - entry) if sl != entry else 0
            if rr < min_rr:
                return None
            return {
                "action": "sell", "entry": entry, "stop_loss": sl, "take_profit": tp,
                "ob_key": f"rsi_ob:sell:{ob.get('break_open_time','?')}:{ob.get('ob_open_time','?')}",
                "risk_reward": rr,
            }
        sl = mid + atr14 * sl_atr
        tp = mid - atr14 * tp_atr
        risk = sl - mid
        reward = mid - tp
        if risk <= 0 or reward / risk < min_rr:
            return None
        return {
            "action": "sell", "entry": mid, "stop_loss": sl, "take_profit": tp,
            "ob_key": f"rsi_atr:sell:{now}", "risk_reward": reward / risk,
        }

    return None
