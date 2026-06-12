from __future__ import annotations

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


def compute_indicators(candles: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [c for c in candles if c.get("is_closed", 1)]
    closes = [float(c["close"]) for c in closed]
    ma60 = sma(closes, 60)
    ma80 = sma(closes, 80)
    ma300 = sma(closes, 300)
    atr14 = atr(closed, 14)
    body20 = avg_body(closed, 20)
    rsi14 = rsi(closes, 14)
    trend = trend_from_ma(ma60, ma80, ma300)
    return {
        "closed_candles": len(closed),
        "ma60": ma60,
        "ma80": ma80,
        "ma300": ma300,
        "atr14": atr14,
        "avg_body20": body20,
        "rsi14": rsi14,
        "trend": trend,
        "ready_for_ma300": len(closed) >= 300,
    }
