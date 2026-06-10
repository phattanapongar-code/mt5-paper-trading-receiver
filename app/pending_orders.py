from __future__ import annotations

import json
import time
from typing import Any

from app import storage
from app.candle_engine import CandleEngine, TIMEFRAMES
from app.config import settings


class PendingOrderEngine:
    """Create and supervise auditable M15 pending-order candidates.

    A pending order is staged only after a live price touches an aligned
    strong M15 Order Block. The engine computes entry/SL/TP/RR, applies safety
    gates, keeps a single active pending order, and cancels stale context.
    """

    ACTIVE_STATUS = "pending"
    FINAL_STATUSES = {"cancelled", "rejected", "filled"}

    def __init__(
        self,
        timeframe: str | None = None,
        expiry_candles: int | None = None,
        min_rr: float | None = None,
        tp_r_multiple: float | None = None,
        sl_buffer_ratio: float | None = None,
        max_spread: float | None = None,
        stale_tick_seconds: int | None = None,
        rejection_log_cooldown: int | None = None,
    ) -> None:
        self.timeframe = (timeframe or settings.pending_timeframe).upper()
        if self.timeframe not in TIMEFRAMES:
            raise ValueError(f"Unsupported pending timeframe: {self.timeframe}")
        self.expiry_candles = settings.pending_expiry_candles if expiry_candles is None else expiry_candles
        self.min_rr = settings.pending_min_rr if min_rr is None else min_rr
        self.tp_r_multiple = settings.pending_tp_r_multiple if tp_r_multiple is None else tp_r_multiple
        self.sl_buffer_ratio = settings.pending_sl_buffer_ratio if sl_buffer_ratio is None else sl_buffer_ratio
        self.max_spread = settings.max_spread if max_spread is None else max_spread
        self.stale_tick_seconds = settings.stale_tick_seconds if stale_tick_seconds is None else stale_tick_seconds
        self.rejection_log_cooldown = (
            settings.pending_rejection_log_cooldown if rejection_log_cooldown is None else rejection_log_cooldown
        )
        self.candles = CandleEngine()

    def on_tick(self, symbol: str, bid: float, ask: float, received_at: int | None = None) -> dict[str, Any]:
        now = int(time.time()) if received_at is None else int(received_at)
        spread = float(ask) - float(bid)
        cancelled = self.cancel_if_needed(symbol=symbol, bid=bid, ask=ask, received_at=now)
        created = None
        rejected = None
        if self.active(symbol) is None:
            created, rejected = self._create_if_touched(symbol=symbol, bid=bid, ask=ask, spread=spread, received_at=now)
        return {"created": created, "cancelled": cancelled, "rejected": rejected}

    def cancel_if_needed(self, symbol: str, bid: float, ask: float, received_at: int | None = None) -> dict[str, Any] | None:
        now = int(time.time()) if received_at is None else int(received_at)
        order = self.active(symbol)
        if order is None:
            return None

        reason = self._cancel_reason(order=order, symbol=symbol, bid=bid, ask=ask, received_at=now)
        if reason is None:
            return None
        return self.cancel(int(order["id"]), reason)

    def cancel(self, order_id: int, reason: str = "manual_cancel") -> dict[str, Any]:
        order = self.by_id(order_id)
        if order is None:
            raise ValueError(f"Pending order not found: {order_id}")
        if order["status"] != self.ACTIVE_STATUS:
            return order
        now = int(time.time())
        storage.execute(
            """
            UPDATE pending_orders
            SET status = 'cancelled', cancel_reason = ?, updated_at = ?
            WHERE id = ?
            """,
            (reason, now, order_id),
        )
        self._log(order["symbol"], order["timeframe"], "pending_cancelled", reason, {"order_id": order_id})
        row = self.by_id(order_id)
        if row is None:
            raise RuntimeError("Cancelled pending order disappeared")
        return row

    def active(self, symbol: str) -> dict[str, Any] | None:
        return storage.query_one(
            """
            SELECT * FROM pending_orders
            WHERE symbol = ? AND status = 'pending'
            ORDER BY id DESC LIMIT 1
            """,
            (symbol,),
        )

    def by_id(self, order_id: int) -> dict[str, Any] | None:
        return storage.query_one("SELECT * FROM pending_orders WHERE id = ?", (order_id,))

    def list(self, symbol: str, limit: int = 50) -> list[dict[str, Any]]:
        return storage.query_all(
            "SELECT * FROM pending_orders WHERE symbol = ? ORDER BY id DESC LIMIT ?",
            (symbol, limit),
        )

    def rejections(self, symbol: str, limit: int = 50) -> list[dict[str, Any]]:
        return storage.query_all(
            """
            SELECT * FROM signal_logs
            WHERE symbol = ? AND event_type = 'pending_rejected'
            ORDER BY id DESC LIMIT ?
            """,
            (symbol, limit),
        )

    def state(self, symbol: str) -> dict[str, Any]:
        counts = storage.query_one(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
                SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected,
                SUM(CASE WHEN status = 'filled' THEN 1 ELSE 0 END) AS filled
            FROM pending_orders WHERE symbol = ?
            """,
            (symbol,),
        ) or {}
        return {
            "symbol": symbol,
            "timeframe": self.timeframe,
            "execution": "AUTO_PAPER_FILL_AVAILABLE_WHEN_ENABLED",
            "rules": {
                "max_active_pending": 1,
                "expiry_candles": self.expiry_candles,
                "min_rr": self.min_rr,
                "tp_r_multiple": self.tp_r_multiple,
                "sl_buffer_ratio": self.sl_buffer_ratio,
                "max_spread": self.max_spread,
                "stale_tick_seconds": self.stale_tick_seconds,
                "rejection_log_cooldown": self.rejection_log_cooldown,
            },
            "active": self.active(symbol),
            "counts": {key: int(counts.get(key) or 0) for key in ["total", "pending", "cancelled", "rejected", "filled"]},
        }

    def _create_if_touched(
        self,
        symbol: str,
        bid: float,
        ask: float,
        spread: float,
        received_at: int,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        if spread > self.max_spread:
            return None, self._reject(symbol, "spread_too_high", {"spread": spread, "max_spread": self.max_spread})
        if int(time.time()) - received_at > self.stale_tick_seconds:
            return None, self._reject(
                symbol, "stale_tick", {"received_at": received_at, "stale_tick_seconds": self.stale_tick_seconds}
            )

        latest_closed = self._latest_closed(symbol)
        if latest_closed is None:
            return None, self._reject(symbol, "missing_closed_candle", {})
        trend = str(self.candles.get_indicators(symbol, self.timeframe)["trend"])
        if trend not in {"BULLISH", "BEARISH"}:
            return None, self._reject(symbol, "trend_not_tradeable", {"trend": trend})

        candidates = storage.query_all(
            """
            SELECT * FROM order_blocks
            WHERE symbol = ? AND timeframe = ?
              AND status IN ('active', 'tested_once')
              AND is_strong = 1
            ORDER BY break_open_time DESC, id DESC
            """,
            (symbol, self.timeframe),
        )
        if not candidates:
            return None, None

        for ob in candidates:
            expected_trend = "BULLISH" if ob["side"] == "bullish" else "BEARISH"
            if trend != expected_trend:
                continue
            if self._existing_for_ob(ob) is not None:
                continue
            if not self._zone_touched(ob=ob, bid=bid, ask=ask):
                continue

            order = self._build_order(ob=ob, trend=trend, spread=spread, created_open_time=int(latest_closed["open_time"]), received_at=received_at)
            if order["risk_reward"] < self.min_rr:
                payload = {"ob_id": int(ob["id"]), "risk_reward": order["risk_reward"], "min_rr": self.min_rr}
                return None, self._reject(symbol, "rr_too_low", payload)
            if self.tp_r_multiple < self.min_rr:
                payload = {"ob_id": int(ob["id"]), "tp_r_multiple": self.tp_r_multiple, "min_rr": self.min_rr}
                return None, self._reject(symbol, "tp_multiple_below_rr_gate", payload)

            cur = storage.execute(
                """
                INSERT INTO pending_orders(
                    symbol, timeframe, side, ob_id, ob_side, ob_break_open_time, source_trend, entry, stop_loss,
                    take_profit, risk_distance, risk_reward, spread_at_creation,
                    created_open_time, expires_open_time, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    symbol,
                    self.timeframe,
                    order["side"],
                    order["ob_id"],
                    str(ob["side"]),
                    int(ob["break_open_time"]),
                    trend,
                    order["entry"],
                    order["stop_loss"],
                    order["take_profit"],
                    order["risk_distance"],
                    order["risk_reward"],
                    spread,
                    order["created_open_time"],
                    order["expires_open_time"],
                    received_at,
                    received_at,
                ),
            )
            created = self.by_id(int(cur.lastrowid))
            self._log(symbol, self.timeframe, "pending_created", "strong_ob_touched", created or {})
            return created, None
        return None, None

    def _build_order(
        self,
        ob: dict[str, Any],
        trend: str,
        spread: float,
        created_open_time: int,
        received_at: int,
    ) -> dict[str, Any]:
        del trend, spread, received_at  # retained in caller for persisted audit fields
        ob_low = float(ob["ob_low"])
        ob_high = float(ob["ob_high"])
        ob_range = ob_high - ob_low
        if ob_range <= 0:
            raise ValueError(f"Invalid OB range for ob_id={ob['id']}")
        entry = (ob_low + ob_high) / 2.0
        buffer = ob_range * self.sl_buffer_ratio
        if ob["side"] == "bullish":
            side = "buy"
            stop_loss = ob_low - buffer
            risk_distance = entry - stop_loss
            take_profit = entry + (risk_distance * self.tp_r_multiple)
        else:
            side = "sell"
            stop_loss = ob_high + buffer
            risk_distance = stop_loss - entry
            take_profit = entry - (risk_distance * self.tp_r_multiple)
        risk_reward = abs(take_profit - entry) / risk_distance
        expires_open_time = created_open_time + (TIMEFRAMES[self.timeframe] * self.expiry_candles)
        return {
            "side": side,
            "ob_id": int(ob["id"]),
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_distance": risk_distance,
            "risk_reward": risk_reward,
            "created_open_time": created_open_time,
            "expires_open_time": expires_open_time,
        }

    def _cancel_reason(self, order: dict[str, Any], symbol: str, bid: float, ask: float, received_at: int) -> str | None:
        spread = float(ask) - float(bid)
        if spread > self.max_spread:
            return "spread_too_high"

        latest_closed = self._latest_closed(symbol)
        if latest_closed is not None and int(latest_closed["open_time"]) >= int(order["expires_open_time"]):
            return "expired_after_candles"
        if int(time.time()) - received_at > self.stale_tick_seconds:
            return "stale_tick"

        ob = storage.query_one(
            """
            SELECT * FROM order_blocks
            WHERE symbol = ? AND timeframe = ? AND side = ? AND break_open_time = ?
            ORDER BY id DESC LIMIT 1
            """,
            (order["symbol"], order["timeframe"], order["ob_side"], order["ob_break_open_time"]),
        )
        if ob is None:
            return "order_block_missing"
        if ob["status"] not in {"active", "tested_once"} or int(ob["is_strong"]) != 1:
            return "order_block_invalidated"

        trend = str(self.candles.get_indicators(symbol, self.timeframe)["trend"])
        if trend != str(order["source_trend"]):
            return "ma_structure_changed"
        return None

    def _latest_closed(self, symbol: str) -> dict[str, Any] | None:
        return storage.query_one(
            """
            SELECT * FROM candles
            WHERE symbol = ? AND timeframe = ? AND is_closed = 1
            ORDER BY open_time DESC LIMIT 1
            """,
            (symbol, self.timeframe),
        )

    @staticmethod
    def _zone_touched(ob: dict[str, Any], bid: float, ask: float) -> bool:
        return float(ask) >= float(ob["ob_low"]) and float(bid) <= float(ob["ob_high"])

    @staticmethod
    def _existing_for_ob(ob: dict[str, Any]) -> dict[str, Any] | None:
        return storage.query_one(
            """
            SELECT * FROM pending_orders
            WHERE symbol = ? AND timeframe = ? AND ob_side = ? AND ob_break_open_time = ?
            ORDER BY id DESC LIMIT 1
            """,
            (ob["symbol"], ob["timeframe"], ob["side"], ob["break_open_time"]),
        )

    def _reject(self, symbol: str, reason: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {"reason": reason, **payload}
        now = int(time.time())
        last = storage.query_one(
            """
            SELECT ts FROM signal_logs
            WHERE symbol = ? AND timeframe = ? AND event_type = 'pending_rejected' AND message = ?
            ORDER BY id DESC LIMIT 1
            """,
            (symbol, self.timeframe, reason),
        )
        should_log = last is None or now - int(last["ts"]) >= self.rejection_log_cooldown
        if should_log:
            self._log(symbol, self.timeframe, "pending_rejected", reason, event)
        return {**event, "logged": should_log}

    @staticmethod
    def _log(symbol: str, timeframe: str, event_type: str, message: str, payload: dict[str, Any]) -> None:
        storage.execute(
            """
            INSERT INTO signal_logs(symbol, timeframe, event_type, message, payload, ts)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (symbol, timeframe, event_type, message, json.dumps(payload, ensure_ascii=False), int(time.time())),
        )
