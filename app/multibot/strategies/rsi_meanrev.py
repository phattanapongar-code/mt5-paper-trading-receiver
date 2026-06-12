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


def decide(conn, bot: dict[str, Any], tick: dict[str, Any], params: dict[str, Any], now: int) -> dict[str, Any] | None:
    """RSI Mean Reversion strategy.

    BUY when RSI exits oversold (<30 crosses to >=30).
    SELL when RSI exits overbought (>70 crosses to <=70).
    SL/TP sized by ATR.
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

    bid = float(tick["bid"])
    ask = float(tick["ask"])
    mid = (bid + ask) / 2

    sl_atr = float(params.get("sl_atr_multiple", 1.5))
    tp_atr = float(params.get("tp_atr_multiple", 3.0))
    min_rr = float(params.get("min_rr", 1.5))
    oversold = float(params.get("rsi_oversold", 30.0))
    overbought = float(params.get("rsi_overbought", 70.0))

    buy_signal = prev_rsi is not None and prev_rsi < oversold <= rsi14
    sell_signal = prev_rsi is not None and prev_rsi > overbought >= rsi14

    if buy_signal:
        sl = mid - atr14 * sl_atr
        tp = mid + atr14 * tp_atr
        risk = mid - sl
        reward = tp - mid
        if risk <= 0 or reward / risk < min_rr:
            return None
        return {
            "action": "buy",
            "entry": mid,
            "stop_loss": sl,
            "take_profit": tp,
            "ob_key": f"rsi_rev:buy:{now}",
            "risk_reward": reward / risk,
        }

    if sell_signal:
        sl = mid + atr14 * sl_atr
        tp = mid - atr14 * tp_atr
        risk = sl - mid
        reward = mid - tp
        if risk <= 0 or reward / risk < min_rr:
            return None
        return {
            "action": "sell",
            "entry": mid,
            "stop_loss": sl,
            "take_profit": tp,
            "ob_key": f"rsi_rev:sell:{now}",
            "risk_reward": reward / risk,
        }

    return None
