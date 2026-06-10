from __future__ import annotations

import time
from typing import Any

from app import storage
from app.config import settings


class PaperEngine:
    def account(self) -> dict[str, Any]:
        row = storage.query_one("SELECT * FROM paper_account WHERE id = 1")
        return row or {"balance": settings.initial_balance, "realized_pnl": 0}

    def open_position(self, symbol: str, side: str, lot: float, bid: float, ask: float,
                      stop_loss: float | None = None, take_profit: float | None = None,
                      note: str = "manual") -> dict[str, Any]:
        entry = ask if side == "buy" else bid
        return self._insert_position(symbol, side, lot, entry, stop_loss, take_profit, note)

    def open_limit_position(self, symbol: str, side: str, lot: float, entry: float,
                            stop_loss: float, take_profit: float, note: str,
                            pending_order_id: int, strategy_id: str, risk_percent: float,
                            risk_usd: float, initial_risk_distance: float) -> dict[str, Any]:
        return self._insert_position(
            symbol, side, lot, entry, stop_loss, take_profit, note,
            pending_order_id=pending_order_id, strategy_id=strategy_id,
            risk_percent=risk_percent, risk_usd=risk_usd,
            initial_risk_distance=initial_risk_distance,
        )

    def _insert_position(self, symbol: str, side: str, lot: float, entry: float,
                         stop_loss: float | None, take_profit: float | None, note: str,
                         pending_order_id: int | None = None, strategy_id: str | None = None,
                         risk_percent: float | None = None, risk_usd: float | None = None,
                         initial_risk_distance: float | None = None) -> dict[str, Any]:
        if self.open_trade() is not None:
            raise ValueError("Only one open position is allowed")
        if side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        if lot <= 0:
            raise ValueError("lot must be > 0")
        now = int(time.time())
        cur = storage.execute(
            """
            INSERT INTO trades(
                symbol, side, lot, entry, stop_loss, take_profit, status, opened_at, note,
                pending_order_id, strategy_id, risk_percent, risk_usd, initial_risk_distance
            ) VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?)
            """,
            (symbol, side, lot, entry, stop_loss, take_profit, now, note,
             pending_order_id, strategy_id, risk_percent, risk_usd, initial_risk_distance),
        )
        return self.trade_by_id(int(cur.lastrowid))

    def close_position(self, bid: float, ask: float, note: str = "manual_close") -> dict[str, Any]:
        trade = self.open_trade()
        if trade is None:
            raise ValueError("No open position")
        exit_price = bid if trade["side"] == "buy" else ask
        pnl = self._pnl(trade, exit_price)
        risk_usd = float(trade.get("risk_usd") or 0.0)
        r_multiple = pnl / risk_usd if risk_usd > 0 else None
        now = int(time.time())
        storage.execute(
            """
            UPDATE trades
            SET exit = ?, status = 'closed', closed_at = ?, pnl = ?,
                note = COALESCE(note, '') || ?, r_multiple = ?, exit_reason = ?
            WHERE id = ?
            """,
            (exit_price, now, pnl, f" | {note}", r_multiple, note, trade["id"]),
        )
        storage.execute(
            """
            UPDATE paper_account
            SET balance = balance + ?, realized_pnl = realized_pnl + ?, updated_at = ?
            WHERE id = 1
            """,
            (pnl, pnl, now),
        )
        return self.trade_by_id(int(trade["id"]))

    def on_tick(self, bid: float, ask: float) -> dict[str, Any] | None:
        trade = self.open_trade()
        if trade is None:
            return None
        if trade["side"] == "buy":
            if trade["stop_loss"] is not None and bid <= trade["stop_loss"]:
                return self.close_position(bid, ask, "sl_hit")
            if trade["take_profit"] is not None and bid >= trade["take_profit"]:
                return self.close_position(bid, ask, "tp_hit")
        else:
            if trade["stop_loss"] is not None and ask >= trade["stop_loss"]:
                return self.close_position(bid, ask, "sl_hit")
            if trade["take_profit"] is not None and ask <= trade["take_profit"]:
                return self.close_position(bid, ask, "tp_hit")
        return None

    def state(self, bid: float | None = None, ask: float | None = None) -> dict[str, Any]:
        account = self.account()
        trade = self.open_trade()
        unrealized = 0.0
        if trade and bid is not None and ask is not None:
            exit_price = bid if trade["side"] == "buy" else ask
            unrealized = self._pnl(trade, exit_price)
        return {
            "balance": account["balance"], "realized_pnl": account["realized_pnl"],
            "unrealized_pnl": unrealized, "equity": account["balance"] + unrealized,
            "open_position": trade,
        }

    def reset(self, balance: float | None = None) -> dict[str, Any]:
        now = int(time.time())
        new_balance = settings.initial_balance if balance is None else balance
        storage.execute("DELETE FROM trades")
        storage.execute("DELETE FROM pending_orders")
        storage.execute("UPDATE paper_account SET balance = ?, realized_pnl = 0, updated_at = ? WHERE id = 1", (new_balance, now))
        return self.account()

    def trades(self, limit: int = 100) -> list[dict[str, Any]]:
        return storage.query_all("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,))

    def open_trade(self) -> dict[str, Any] | None:
        return storage.query_one("SELECT * FROM trades WHERE status = 'open' ORDER BY id DESC LIMIT 1")

    def trade_by_id(self, trade_id: int) -> dict[str, Any]:
        row = storage.query_one("SELECT * FROM trades WHERE id = ?", (trade_id,))
        if row is None:
            raise ValueError(f"Trade not found: {trade_id}")
        return row

    @staticmethod
    def _pnl(trade: dict[str, Any], exit_price: float) -> float:
        points = exit_price - trade["entry"] if trade["side"] == "buy" else trade["entry"] - exit_price
        return points * trade["lot"] * settings.contract_size
