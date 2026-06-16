from __future__ import annotations

from typing import Any

from app import storage
from app.indicators import compute_indicators


def _ma_candles(symbol: str, timeframe: str) -> list[dict[str, Any]]:
    if not storage.table_exists("candles"):
        return []
    rows = storage.query_all(
        "SELECT open, high, low, close, is_closed FROM candles WHERE symbol=? AND timeframe=? AND is_closed=1 ORDER BY open_time DESC LIMIT 300",
        (symbol, timeframe),
    )
    return list(reversed(rows)) if rows else []


def decide(conn, bot: dict[str, Any], tick: dict[str, Any], params: dict[str, Any], now: int) -> dict[str, Any] | None:
    """MA Crossover strategy.

    BUY when MA60 crosses above MA80 (short-term uptrend).
    SELL when MA60 crosses below MA80 (short-term downtrend).
    Uses the ATR for SL/TP placement.
    """
    candles = _ma_candles(bot["symbol"], bot["timeframe"])
    if len(candles) < 80:
        return None

    ind = compute_indicators(candles)
    ma60 = ind.get("ma60")
    ma80 = ind.get("ma80")
    atr14 = ind.get("atr14")
    if ma60 is None or ma80 is None or atr14 is None:
        return None

    # Get previous candle's MAs for cross detection
    prev_candles = candles[:-1] if len(candles) > 80 else candles
    prev_ind = compute_indicators(prev_candles)
    prev_ma60 = prev_ind.get("ma60")
    prev_ma80 = prev_ind.get("ma80")

    bid = float(tick["bid"])
    ask = float(tick["ask"])
    mid = (bid + ask) / 2

    atr = atr14
    sl_atr = float(params.get("sl_atr_multiple", 1.5))
    tp_atr = float(params.get("tp_atr_multiple", 3.0))
    min_rr = float(params.get("min_rr", 1.5))

    # Detect cross: current > prev means ma60 crossed above
    curr_diff = ma60 - ma80
    prev_diff = (prev_ma60 - prev_ma80) if prev_ma60 is not None and prev_ma80 is not None else 0.0

    long_signal = prev_diff <= 0 < curr_diff
    short_signal = prev_diff >= 0 > curr_diff

    if long_signal:
        sl = mid - atr * sl_atr
        tp = mid + atr * tp_atr
        risk = mid - sl
        reward = tp - mid
        if risk <= 0 or reward / risk < min_rr:
            return None
        return {
            "action": "buy",
            "entry": mid,
            "stop_loss": sl,
            "take_profit": tp,
            "ob_key": f"ma_cross:buy:{now}",
            "risk_reward": reward / risk,
        }

    if short_signal:
        sl = mid + atr * sl_atr
        tp = mid - atr * tp_atr
        risk = sl - mid
        reward = mid - tp
        if risk <= 0 or reward / risk < min_rr:
            return None
        return {
            "action": "sell",
            "entry": mid,
            "stop_loss": sl,
            "take_profit": tp,
            "ob_key": f"ma_cross:sell:{now}",
            "risk_reward": reward / risk,
        }

    return None
