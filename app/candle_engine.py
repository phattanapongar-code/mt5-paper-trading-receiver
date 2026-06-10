from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Iterable

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

    def import_m1_history(self, symbol: str, rows: Iterable[dict[str, Any]]) -> dict[str, int]:
        now = int(time.time())
        normalized: list[tuple[Any, ...]] = []
        for row in rows:
            open_time = self._bucket(int(row["open_time"]), 60)
            normalized.append(
                (
                    symbol,
                    "M1",
                    open_time,
                    open_time + 60,
                    float(row["open"]),
                    float(row["high"]),
                    float(row["low"]),
                    float(row["close"]),
                    int(row.get("tick_volume", 0)),
                    1,
                    now,
                )
            )

        with storage.transaction() as conn:
            conn.executemany(
                """
                INSERT INTO candles(symbol, timeframe, open_time, close_time, open, high, low, close, tick_count, is_closed, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, timeframe, open_time) DO UPDATE SET
                    close_time = excluded.close_time,
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    tick_count = excluded.tick_count,
                    is_closed = 1,
                    updated_at = excluded.updated_at
                """,
                normalized,
            )

        rebuilt = self.rebuild_from_m1(symbol)
        return {"imported_m1": len(normalized), **rebuilt}

    def rebuild_from_m1(self, symbol: str) -> dict[str, int]:
        m1_rows = storage.query_all(
            """
            SELECT * FROM candles
            WHERE symbol = ? AND timeframe = 'M1' AND is_closed = 1
            ORDER BY open_time ASC
            """,
            (symbol,),
        )
        result: dict[str, int] = {}
        for timeframe in ["M5", "M15", "H1"]:
            result[f"rebuilt_{timeframe.lower()}"] = self._rebuild_timeframe(symbol, timeframe, m1_rows)
        return result

    def _rebuild_timeframe(self, symbol: str, timeframe: str, m1_rows: list[dict[str, Any]]) -> int:
        seconds = TIMEFRAMES[timeframe]
        required_count = seconds // 60
        groups: dict[int, list[dict[str, Any]]] = {}
        for row in m1_rows:
            bucket = self._bucket(int(row["open_time"]), seconds)
            groups.setdefault(bucket, []).append(row)

        now = int(time.time())
        values: list[tuple[Any, ...]] = []
        for open_time, rows in sorted(groups.items()):
            rows.sort(key=lambda r: int(r["open_time"]))
            expected = [open_time + i * 60 for i in range(required_count)]
            actual = [int(r["open_time"]) for r in rows]
            if actual != expected:
                # Reject incomplete bars around weekends, session gaps, and partial history edges.
                continue
            values.append(
                (
                    symbol,
                    timeframe,
                    open_time,
                    open_time + seconds,
                    float(rows[0]["open"]),
                    max(float(r["high"]) for r in rows),
                    min(float(r["low"]) for r in rows),
                    float(rows[-1]["close"]),
                    sum(int(r["tick_count"]) for r in rows),
                    1,
                    now,
                )
            )

        if values:
            with storage.transaction() as conn:
                conn.executemany(
                    """
                    INSERT INTO candles(symbol, timeframe, open_time, close_time, open, high, low, close, tick_count, is_closed, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol, timeframe, open_time) DO UPDATE SET
                        close_time = excluded.close_time,
                        open = excluded.open,
                        high = excluded.high,
                        low = excluded.low,
                        close = excluded.close,
                        tick_count = excluded.tick_count,
                        is_closed = 1,
                        updated_at = excluded.updated_at
                    """,
                    values,
                )
        return len(values)

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
        rows = self.get_candles(symbol, timeframe, limit=400, closed_only=True)
        return compute_indicators(rows)
