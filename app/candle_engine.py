from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from typing import Any

from app import storage
from app.indicators import compute_indicators

TIMEFRAMES: dict[str, int] = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "H1": 3600,
}


@dataclass
class Candle:
    symbol: str
    timeframe: str
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    tick_count: int
    is_closed: int = 0
    updated_at: int = 0


class CandleEngine:
    def __init__(self) -> None:
        self.active: dict[tuple[str, str], Candle] = {}

    @staticmethod
    def _bucket(ts: int, seconds: int) -> int:
        return int(ts - (ts % seconds))

    def update_tick(self, symbol: str, bid: float, ask: float, ts: int) -> dict[str, Any]:
        mid = (bid + ask) / 2
        closed: list[dict[str, Any]] = []
        current: dict[str, dict[str, Any]] = {}

        for tf, seconds in TIMEFRAMES.items():
            key = (symbol, tf)
            open_time = self._bucket(ts, seconds)
            close_time = open_time + seconds
            candle = self.active.get(key)

            if candle is None:
                candle = self._load_active(symbol, tf, open_time)
                if candle is not None:
                    self.active[key] = candle

            if candle is None or candle.open_time < open_time:
                if candle is not None:
                    candle.is_closed = 1
                    candle.close_time = candle.open_time + seconds
                    candle.updated_at = int(time.time())
                    self._upsert(candle)
                    closed.append(asdict(candle))

                candle = Candle(
                    symbol=symbol,
                    timeframe=tf,
                    open_time=open_time,
                    close_time=close_time,
                    open=mid,
                    high=mid,
                    low=mid,
                    close=mid,
                    tick_count=1,
                    is_closed=0,
                    updated_at=int(time.time()),
                )
                self.active[key] = candle
            else:
                candle.high = max(candle.high, mid)
                candle.low = min(candle.low, mid)
                candle.close = mid
                candle.tick_count += 1
                candle.updated_at = int(time.time())

            self._upsert(candle)
            current[tf] = asdict(candle)

        return {"closed": closed, "current": current}

    def _load_active(self, symbol: str, timeframe: str, open_time: int) -> Candle | None:
        row = storage.query_one(
            """
            SELECT * FROM candles
            WHERE symbol = ? AND timeframe = ? AND open_time = ? AND is_closed = 0
            """,
            (symbol, timeframe, open_time),
        )
        if not row:
            return None
        return Candle(
            symbol=row["symbol"], timeframe=row["timeframe"], open_time=row["open_time"],
            close_time=row["close_time"], open=row["open"], high=row["high"],
            low=row["low"], close=row["close"], tick_count=row["tick_count"],
            is_closed=row["is_closed"], updated_at=row["updated_at"],
        )

    def _upsert(self, candle: Candle) -> None:
        storage.execute(
            """
            INSERT INTO candles(symbol, timeframe, open_time, close_time, open, high, low, close, tick_count, is_closed, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, timeframe, open_time) DO UPDATE SET
                close_time = excluded.close_time,
                high = excluded.high,
                low = excluded.low,
                close = excluded.close,
                tick_count = excluded.tick_count,
                is_closed = excluded.is_closed,
                updated_at = excluded.updated_at
            """,
            (candle.symbol, candle.timeframe, candle.open_time, candle.close_time, candle.open,
             candle.high, candle.low, candle.close, candle.tick_count, candle.is_closed, candle.updated_at),
        )

    def get_candles(self, symbol: str, timeframe: str, limit: int = 400, closed_only: bool = False) -> list[dict[str, Any]]:
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        if closed_only:
            rows = storage.query_all(
                """
                SELECT * FROM candles
                WHERE symbol = ? AND timeframe = ? AND is_closed = 1
                ORDER BY open_time DESC LIMIT ?
                """,
                (symbol, timeframe, limit),
            )
        else:
            rows = storage.query_all(
                """
                SELECT * FROM candles
                WHERE symbol = ? AND timeframe = ?
                ORDER BY open_time DESC LIMIT ?
                """,
                (symbol, timeframe, limit),
            )
        return list(reversed(rows))

    def get_indicators(self, symbol: str, timeframe: str) -> dict[str, Any]:
        candles = self.get_candles(symbol, timeframe, limit=400, closed_only=True)
        return compute_indicators(candles)
