from __future__ import annotations

import math
from typing import Any


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def atr(candles: list[dict[str, Any]], period: int = 14) -> float | None:
    if len(candles) < period + 1:
        return None
    trs: list[float] = []
    tail = candles[-(period + 1):]
    for i in range(1, len(tail)):
        cur = tail[i]
        prev = tail[i - 1]
        tr = max(
            cur["high"] - cur["low"],
            abs(cur["high"] - prev["close"]),
            abs(cur["low"] - prev["close"]),
        )
        trs.append(tr)
    return sum(trs) / len(trs)


def avg_body(candles: list[dict[str, Any]], period: int = 20) -> float | None:
    if len(candles) < period:
        return None
    bodies = [abs(c["close"] - c["open"]) for c in candles[-period:]]
    return sum(bodies) / len(bodies)


def rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for i in range(1, period + 1):
        diff = closes[-i] - closes[-i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def trend_from_ma(ma60: float | None, ma80: float | None, ma300: float | None) -> str:
    if ma60 is None or ma80 is None or ma300 is None:
        return "WARMING_UP"
    if ma60 > ma80 > ma300:
        return "BULLISH"
    if ma60 < ma80 < ma300:
        return "BEARISH"
    if ma60 > ma80:
        return "BULLISH"
    if ma60 < ma80:
        return "BEARISH"
    return "NEUTRAL"


def ema(values: list[float], period: int) -> list[float]:
    if len(values) < period:
        return []
    multiplier = 2.0 / (period + 1)
    result = [sum(values[:period]) / period]
    for v in values[period:]:
        result.append((v - result[-1]) * multiplier + result[-1])
    return result


def macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, float | None]:
    if len(closes) < slow + signal:
        return {"macd": None, "macd_signal": None, "macd_histogram": None}
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    if not ema_fast or not ema_slow:
        return {"macd": None, "macd_signal": None, "macd_histogram": None}
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = ema(macd_line, signal)
    if not signal_line:
        return {"macd": None, "macd_signal": None, "macd_histogram": None}
    return {
        "macd": macd_line[-1],
        "macd_signal": signal_line[-1],
        "macd_histogram": macd_line[-1] - signal_line[-1],
    }


def bollinger_bands(closes: list[float], period: int = 20, std_dev: float = 2.0) -> dict[str, float | None]:
    if len(closes) < period:
        return {"bb_upper": None, "bb_middle": None, "bb_lower": None}
    sma_val = sma(closes, period)
    if sma_val is None:
        return {"bb_upper": None, "bb_middle": None, "bb_lower": None}
    window = closes[-period:]
    variance = sum((x - sma_val) ** 2 for x in window) / period
    std = math.sqrt(variance)
    return {
        "bb_upper": round(sma_val + std_dev * std, 2),
        "bb_middle": round(sma_val, 2),
        "bb_lower": round(sma_val - std_dev * std, 2),
    }


def compute_indicators(candles: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [c for c in candles if c.get("is_closed", 1)]
    closes = [float(c["close"]) for c in closed]
    ma60 = sma(closes, 60)
    ma80 = sma(closes, 80)
    ma300 = sma(closes, 300)
    atr14 = atr(closed, 14)
    body20 = avg_body(closed, 20)
    rsi14 = rsi(closes, 14)
    macd_result = macd(closes)
    bb_result = bollinger_bands(closes)
    trend = trend_from_ma(ma60, ma80, ma300)
    return {
        "closed_candles": len(closed),
        "ma60": ma60,
        "ma80": ma80,
        "ma300": ma300,
        "atr14": atr14,
        "avg_body20": body20,
        "rsi14": rsi14,
        "macd": macd_result["macd"],
        "macd_signal": macd_result["macd_signal"],
        "macd_histogram": macd_result["macd_histogram"],
        "bb_upper": bb_result["bb_upper"],
        "bb_middle": bb_result["bb_middle"],
        "bb_lower": bb_result["bb_lower"],
        "trend": trend,
        "ready_for_ma300": len(closed) >= 300,
    }
