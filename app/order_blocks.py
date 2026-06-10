from __future__ import annotations

import time
from typing import Any

from app import storage
from app.candle_engine import TIMEFRAMES
from app.config import settings
from app.indicators import atr, avg_body


class OrderBlockEngine:
    """Build auditable Order Block candidates from confirmed BOS events.

    v0.5 deliberately stops before order placement. It detects structural OB
    candidates, evaluates impulse quality, tracks closed-candle retests and
    invalidation, and stores an explainable score. RR is applied later when an
    executable entry and SL exist in the pending-order layer.
    """

    VALID_STATUSES = {"active", "tested_once", "invalidated", "expired"}

    def __init__(
        self,
        lookback: int | None = None,
        impulse_body: float | None = None,
        impulse_range: float | None = None,
        swing_tolerance: float | None = None,
        strong_score: int | None = None,
        max_age_candles: int | None = None,
        scan_limit: int | None = None,
    ) -> None:
        self.lookback = lookback or settings.ob_lookback
        self.impulse_body = impulse_body or settings.impulse_body
        self.impulse_range = impulse_range or settings.impulse_range
        self.swing_tolerance = swing_tolerance if swing_tolerance is not None else settings.swing_tolerance
        self.strong_score = strong_score or settings.ob_strong_score
        self.max_age_candles = settings.ob_max_age_candles if max_age_candles is None else max_age_candles
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

        bos_events = storage.query_all(
            """
            SELECT * FROM bos_events
            WHERE symbol = ? AND timeframe = ?
            ORDER BY break_open_time ASC, id ASC
            """,
            (symbol, timeframe),
        )

        with storage.transaction() as conn:
            conn.execute("DELETE FROM order_blocks WHERE symbol = ? AND timeframe = ?", (symbol, timeframe))

        if not candles or not bos_events:
            return self._summary(symbol, timeframe)

        index_by_time = {int(c["open_time"]): i for i, c in enumerate(candles)}
        now = int(time.time())
        values: list[tuple[Any, ...]] = []

        for bos in bos_events:
            break_time = int(bos["break_open_time"])
            break_index = index_by_time.get(break_time)
            if break_index is None or break_index < 1:
                continue

            ob_index = self._find_origin_index(candles, break_index, str(bos["side"]))
            if ob_index is None:
                continue

            ob = candles[ob_index]
            side = str(bos["side"])
            ob_low = float(ob["low"])
            ob_high = float(ob["high"])
            atr14 = atr(candles[: break_index + 1], 14)
            body20 = avg_body(candles[:break_index], 20)
            impulse_segment = candles[ob_index + 1 : break_index + 1]
            if not impulse_segment:
                continue

            impulse_body_value = abs(float(candles[break_index]["close"]) - float(ob["close"]))
            impulse_range_value = max(float(c["high"]) for c in impulse_segment) - min(float(c["low"]) for c in impulse_segment)
            impulse_body_ratio = None if not body20 or body20 <= 0 else impulse_body_value / body20
            impulse_range_ratio = None if not atr14 or atr14 <= 0 else impulse_range_value / atr14

            swing = self._origin_swing(symbol, timeframe, side, int(ob["open_time"]))
            swing_distance_ratio = None
            if swing is not None and atr14 and atr14 > 0:
                edge = ob_low if side == "bullish" else ob_high
                swing_distance_ratio = abs(edge - float(swing["price"])) / atr14

            retest_count, status = self._classify_lifecycle(candles, break_index, side, ob_low, ob_high)
            score, score_reasons = self._score(
                retest_count=retest_count,
                impulse_body_ratio=impulse_body_ratio,
                impulse_range_ratio=impulse_range_ratio,
                swing_distance_ratio=swing_distance_ratio,
            )
            is_strong = int(score >= self.strong_score and status in {"active", "tested_once"})

            values.append(
                (
                    symbol,
                    timeframe,
                    side,
                    int(bos["id"]),
                    int(bos["swing_open_time"]),
                    float(bos["swing_price"]),
                    break_time,
                    float(bos["break_close"]),
                    int(ob["open_time"]),
                    float(ob["open"]),
                    float(ob["close"]),
                    ob_low,
                    ob_high,
                    impulse_body_value,
                    impulse_range_value,
                    impulse_body_ratio,
                    impulse_range_ratio,
                    None if swing is None else int(swing["pivot_open_time"]),
                    None if swing is None else float(swing["price"]),
                    swing_distance_ratio,
                    retest_count,
                    status,
                    score,
                    is_strong,
                    ",".join(score_reasons),
                    now,
                    now,
                )
            )

        if values:
            storage.executemany(
                """
                INSERT INTO order_blocks(
                    symbol, timeframe, side, bos_id, swing_open_time, swing_price,
                    break_open_time, break_close, ob_open_time, ob_open, ob_close,
                    ob_low, ob_high, impulse_body, impulse_range, impulse_body_ratio,
                    impulse_range_ratio, origin_swing_open_time, origin_swing_price,
                    swing_distance_ratio, retest_count, status, score, is_strong,
                    score_reasons, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )

        return self._summary(symbol, timeframe)

    def rebuild_all(self, symbol: str) -> dict[str, dict[str, int]]:
        return {tf: self.rebuild(symbol, tf) for tf in TIMEFRAMES}

    def refresh_timeframes(self, symbol: str, timeframes: list[str]) -> dict[str, dict[str, int]]:
        unique = list(dict.fromkeys(tf.upper() for tf in timeframes if tf.upper() in TIMEFRAMES))
        return {tf: self.rebuild(symbol, tf) for tf in unique}

    def get_order_blocks(self, symbol: str, timeframe: str, limit: int = 50) -> list[dict[str, Any]]:
        self._validate_timeframe(timeframe)
        return storage.query_all(
            """
            SELECT * FROM order_blocks
            WHERE symbol = ? AND timeframe = ?
            ORDER BY break_open_time DESC, id DESC
            LIMIT ?
            """,
            (symbol, timeframe, limit),
        )

    def get_active(self, symbol: str, timeframe: str, limit: int = 50) -> list[dict[str, Any]]:
        self._validate_timeframe(timeframe)
        return storage.query_all(
            """
            SELECT * FROM order_blocks
            WHERE symbol = ? AND timeframe = ?
              AND status IN ('active', 'tested_once')
              AND is_strong = 1
            ORDER BY break_open_time DESC, id DESC
            LIMIT ?
            """,
            (symbol, timeframe, limit),
        )

    def state(self, symbol: str, timeframe: str) -> dict[str, Any]:
        self._validate_timeframe(timeframe)
        latest = storage.query_one(
            """
            SELECT * FROM order_blocks
            WHERE symbol = ? AND timeframe = ?
            ORDER BY break_open_time DESC, id DESC LIMIT 1
            """,
            (symbol, timeframe),
        )
        latest_active = storage.query_one(
            """
            SELECT * FROM order_blocks
            WHERE symbol = ? AND timeframe = ?
              AND status IN ('active', 'tested_once') AND is_strong = 1
            ORDER BY break_open_time DESC, id DESC LIMIT 1
            """,
            (symbol, timeframe),
        )
        counts = self._summary(symbol, timeframe)
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "rr_gate": "DEFERRED_TO_V06_PENDING_ORDER",
            "latest": latest,
            "latest_active_strong": latest_active,
            "counts": counts,
        }

    def _summary(self, symbol: str, timeframe: str) -> dict[str, int]:
        row = storage.query_one(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN is_strong = 1 THEN 1 ELSE 0 END) AS strong,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active,
                SUM(CASE WHEN status = 'tested_once' THEN 1 ELSE 0 END) AS tested_once,
                SUM(CASE WHEN status = 'invalidated' THEN 1 ELSE 0 END) AS invalidated,
                SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END) AS expired
            FROM order_blocks
            WHERE symbol = ? AND timeframe = ?
            """,
            (symbol, timeframe),
        ) or {}
        return {key: int(row.get(key) or 0) for key in ["total", "strong", "active", "tested_once", "invalidated", "expired"]}

    def _find_origin_index(self, candles: list[dict[str, Any]], break_index: int, side: str) -> int | None:
        start = max(0, break_index - self.lookback)
        for i in range(break_index - 1, start - 1, -1):
            candle = candles[i]
            open_ = float(candle["open"])
            close = float(candle["close"])
            if side == "bullish" and close < open_:
                return i
            if side == "bearish" and close > open_:
                return i
        return None

    def _origin_swing(self, symbol: str, timeframe: str, side: str, ob_open_time: int) -> dict[str, Any] | None:
        swing_side = "low" if side == "bullish" else "high"
        return storage.query_one(
            """
            SELECT * FROM swing_points
            WHERE symbol = ? AND timeframe = ? AND side = ? AND pivot_open_time <= ?
            ORDER BY pivot_open_time DESC LIMIT 1
            """,
            (symbol, timeframe, swing_side, ob_open_time),
        )

    def _classify_lifecycle(
        self,
        candles: list[dict[str, Any]],
        break_index: int,
        side: str,
        ob_low: float,
        ob_high: float,
    ) -> tuple[int, str]:
        retests = 0
        later = candles[break_index + 1 :]
        for candle in later:
            close = float(candle["close"])
            high = float(candle["high"])
            low = float(candle["low"])
            if side == "bullish" and close < ob_low:
                return retests, "invalidated"
            if side == "bearish" and close > ob_high:
                return retests, "invalidated"
            if high >= ob_low and low <= ob_high:
                retests += 1
                if retests > 1:
                    return retests, "invalidated"

        if self.max_age_candles > 0 and len(later) > self.max_age_candles:
            return retests, "expired"
        if retests == 1:
            return retests, "tested_once"
        return retests, "active"

    def _score(
        self,
        retest_count: int,
        impulse_body_ratio: float | None,
        impulse_range_ratio: float | None,
        swing_distance_ratio: float | None,
    ) -> tuple[int, list[str]]:
        score = 2  # BOS confirmed by construction.
        reasons = ["bos_confirmed:+2"]

        if retest_count == 0:
            score += 2
            reasons.append("fresh:+2")
            score += 1
            reasons.append("untested:+1")
        elif retest_count == 1:
            score += 1
            reasons.append("tested_once:+1")
        else:
            reasons.append("multiple_retests:+0")

        if impulse_body_ratio is not None and impulse_body_ratio >= self.impulse_body:
            score += 1
            reasons.append("impulse_body:+1")
        else:
            reasons.append("impulse_body:+0")

        if impulse_range_ratio is not None and impulse_range_ratio >= self.impulse_range:
            score += 1
            reasons.append("impulse_range:+1")
        else:
            reasons.append("impulse_range:+0")

        if swing_distance_ratio is not None and swing_distance_ratio <= self.swing_tolerance:
            score += 1
            reasons.append("near_swing:+1")
        else:
            reasons.append("near_swing:+0")

        return score, reasons

    @staticmethod
    def _validate_timeframe(timeframe: str) -> None:
        if timeframe not in TIMEFRAMES:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
