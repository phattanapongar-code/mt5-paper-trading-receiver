from __future__ import annotations

import time
from typing import Any

from app import storage
from app.candle_engine import TIMEFRAMES
from app.config import settings


class MarketStructureEngine:
    """Detect confirmed swing points and BOS events from closed candles only.

    A swing is confirmed only after `swing_window` candles have closed on both
    sides of the pivot. A BOS is confirmed only when a closed candle crosses a
    previously confirmed swing using its close price. Wick-only breaks are not
    treated as BOS.
    """

    def __init__(self, swing_window: int | None = None, scan_limit: int | None = None) -> None:
        self.swing_window = swing_window or settings.swing_window
        self.scan_limit = scan_limit or settings.structure_scan_limit

    def rebuild(self, symbol: str, timeframe: str) -> dict[str, int]:
        self._validate_timeframe(timeframe)
        candles = storage.query_all(
            """
            SELECT * FROM candles
            WHERE symbol = ? AND timeframe = ? AND is_closed = 1
            ORDER BY open_time ASC
            """,
            (symbol, timeframe),
        )
        if self.scan_limit > 0:
            candles = candles[-self.scan_limit :]

        with storage.transaction() as conn:
            conn.execute("DELETE FROM bos_events WHERE symbol = ? AND timeframe = ?", (symbol, timeframe))
            conn.execute("DELETE FROM swing_points WHERE symbol = ? AND timeframe = ?", (symbol, timeframe))

        swing_count = self._detect_and_store_swings(symbol, timeframe, candles)
        bos_count = self._detect_and_store_bos(symbol, timeframe, candles)
        return {"swings": swing_count, "bos": bos_count}

    def rebuild_all(self, symbol: str) -> dict[str, dict[str, int]]:
        return {tf: self.rebuild(symbol, tf) for tf in TIMEFRAMES}

    def refresh_timeframes(self, symbol: str, timeframes: list[str]) -> dict[str, dict[str, int]]:
        unique = list(dict.fromkeys(tf.upper() for tf in timeframes if tf.upper() in TIMEFRAMES))
        return {tf: self.rebuild(symbol, tf) for tf in unique}

    def get_swings(self, symbol: str, timeframe: str, limit: int = 50) -> list[dict[str, Any]]:
        self._validate_timeframe(timeframe)
        return storage.query_all(
            """
            SELECT * FROM swing_points
            WHERE symbol = ? AND timeframe = ?
            ORDER BY pivot_open_time DESC, id DESC
            LIMIT ?
            """,
            (symbol, timeframe, limit),
        )

    def get_bos(self, symbol: str, timeframe: str, limit: int = 50) -> list[dict[str, Any]]:
        self._validate_timeframe(timeframe)
        return storage.query_all(
            """
            SELECT * FROM bos_events
            WHERE symbol = ? AND timeframe = ?
            ORDER BY break_open_time DESC, id DESC
            LIMIT ?
            """,
            (symbol, timeframe, limit),
        )

    def state(self, symbol: str, timeframe: str) -> dict[str, Any]:
        self._validate_timeframe(timeframe)
        latest_high = storage.query_one(
            """
            SELECT * FROM swing_points
            WHERE symbol = ? AND timeframe = ? AND side = 'high'
            ORDER BY pivot_open_time DESC LIMIT 1
            """,
            (symbol, timeframe),
        )
        latest_low = storage.query_one(
            """
            SELECT * FROM swing_points
            WHERE symbol = ? AND timeframe = ? AND side = 'low'
            ORDER BY pivot_open_time DESC LIMIT 1
            """,
            (symbol, timeframe),
        )
        latest_bos = storage.query_one(
            """
            SELECT * FROM bos_events
            WHERE symbol = ? AND timeframe = ?
            ORDER BY break_open_time DESC, id DESC LIMIT 1
            """,
            (symbol, timeframe),
        )
        counts = storage.query_one(
            """
            SELECT
                (SELECT COUNT(*) FROM swing_points WHERE symbol = ? AND timeframe = ?) AS swings,
                (SELECT COUNT(*) FROM bos_events WHERE symbol = ? AND timeframe = ?) AS bos
            """,
            (symbol, timeframe, symbol, timeframe),
        )
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "swing_window": self.swing_window,
            "latest_swing_high": latest_high,
            "latest_swing_low": latest_low,
            "latest_bos": latest_bos,
            "counts": counts or {"swings": 0, "bos": 0},
        }

    def _detect_and_store_swings(self, symbol: str, timeframe: str, candles: list[dict[str, Any]]) -> int:
        w = self.swing_window
        if len(candles) < (w * 2 + 1):
            return 0
        rows: list[tuple[Any, ...]] = []
        created_at = int(time.time())
        for i in range(w, len(candles) - w):
            pivot = candles[i]
            left = candles[i - w : i]
            right = candles[i + 1 : i + 1 + w]
            neighbors = left + right
            pivot_high = float(pivot["high"])
            pivot_low = float(pivot["low"])

            # Strict comparisons prevent ambiguous duplicate plateaus.
            if all(pivot_high > float(c["high"]) for c in neighbors):
                rows.append((symbol, timeframe, "high", int(pivot["open_time"]), pivot_high, created_at))
            if all(pivot_low < float(c["low"]) for c in neighbors):
                rows.append((symbol, timeframe, "low", int(pivot["open_time"]), pivot_low, created_at))

        if rows:
            storage.executemany(
                """
                INSERT OR IGNORE INTO swing_points(symbol, timeframe, side, pivot_open_time, price, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def _detect_and_store_bos(self, symbol: str, timeframe: str, candles: list[dict[str, Any]]) -> int:
        swings = storage.query_all(
            """
            SELECT * FROM swing_points
            WHERE symbol = ? AND timeframe = ?
            ORDER BY pivot_open_time ASC, id ASC
            """,
            (symbol, timeframe),
        )
        if not candles or not swings:
            return 0

        created_at = int(time.time())
        rows: list[tuple[Any, ...]] = []
        latest_high: dict[str, Any] | None = None
        latest_low: dict[str, Any] | None = None
        high_broken_for_pivot: int | None = None
        low_broken_for_pivot: int | None = None
        swing_index = 0

        for i, candle in enumerate(candles):
            open_time = int(candle["open_time"])
            # A swing can only be used after it has enough right-side candles
            # to be confirmed; otherwise historical rebuild would introduce
            # look-ahead bias.
            confirmed_before = open_time - (self.swing_window * TIMEFRAMES[timeframe])
            while swing_index < len(swings) and int(swings[swing_index]["pivot_open_time"]) <= confirmed_before:
                swing = swings[swing_index]
                if swing["side"] == "high":
                    latest_high = swing
                    high_broken_for_pivot = None
                else:
                    latest_low = swing
                    low_broken_for_pivot = None
                swing_index += 1

            if i == 0:
                continue
            prev_close = float(candles[i - 1]["close"])
            close = float(candle["close"])

            if latest_high is not None:
                pivot_time = int(latest_high["pivot_open_time"])
                level = float(latest_high["price"])
                if prev_close <= level < close and high_broken_for_pivot != pivot_time:
                    rows.append((symbol, timeframe, "bullish", pivot_time, level, open_time, close, created_at))
                    high_broken_for_pivot = pivot_time

            if latest_low is not None:
                pivot_time = int(latest_low["pivot_open_time"])
                level = float(latest_low["price"])
                if prev_close >= level > close and low_broken_for_pivot != pivot_time:
                    rows.append((symbol, timeframe, "bearish", pivot_time, level, open_time, close, created_at))
                    low_broken_for_pivot = pivot_time

        if rows:
            storage.executemany(
                """
                INSERT OR IGNORE INTO bos_events(
                    symbol, timeframe, side, swing_open_time, swing_price,
                    break_open_time, break_close, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    @staticmethod
    def _validate_timeframe(timeframe: str) -> None:
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
