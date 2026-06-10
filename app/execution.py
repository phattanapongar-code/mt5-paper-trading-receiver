from __future__ import annotations

import math
import time
from typing import Any

from app import storage
from app.config import settings
from app.paper_engine import PaperEngine
from app.pending_orders import PendingOrderEngine


class AutoPaperExecutionEngine:
    """Fill staged limit orders into the paper account only when enabled.

    This never sends an order back to MT5. It is deliberately paper-only.
    """

    def __init__(self, paper: PaperEngine, pending: PendingOrderEngine) -> None:
        self.paper = paper
        self.pending = pending
        self.enabled = bool(settings.auto_paper_enabled)

    def set_enabled(self, enabled: bool) -> dict[str, Any]:
        self.enabled = bool(enabled)
        return self.state()

    def state(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "mode": "PAPER_ONLY",
            "risk_percent": settings.trend_risk_percent,
            "contract_size": settings.contract_size,
            "lot_step": settings.lot_step,
            "min_lot": settings.min_lot,
            "max_lot": settings.max_lot,
        }

    def on_tick(self, symbol: str, bid: float, ask: float) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        if self.paper.open_trade() is not None:
            return None
        order = self.pending.active(symbol)
        if order is None or not self._triggered(order, bid, ask):
            return None
        lot, risk_usd = self._lot_for_order(order)
        if lot < settings.min_lot:
            return self.pending.cancel(int(order["id"]), "lot_below_minimum")
        trade = self.paper.open_limit_position(
            symbol=symbol,
            side=str(order["side"]),
            lot=lot,
            entry=float(order["entry"]),
            stop_loss=float(order["stop_loss"]),
            take_profit=float(order["take_profit"]),
            note=f"auto_fill pending_order_id={order['id']}",
            pending_order_id=int(order["id"]),
            strategy_id="trend_ob_m15_v1",
            risk_percent=settings.trend_risk_percent,
            risk_usd=risk_usd,
            initial_risk_distance=float(order["risk_distance"]),
        )
        now = int(time.time())
        storage.execute(
            """
            UPDATE pending_orders
            SET status = 'filled', filled_at = ?, fill_price = ?, trade_id = ?, updated_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (now, float(order["entry"]), int(trade["id"]), now, int(order["id"])),
        )
        return {"event": "auto_paper_filled", "pending_order": self.pending.by_id(int(order["id"])), "trade": trade}

    @staticmethod
    def _triggered(order: dict[str, Any], bid: float, ask: float) -> bool:
        if order["side"] == "buy":
            return float(ask) <= float(order["entry"])
        return float(bid) >= float(order["entry"])

    @staticmethod
    def _round_down(value: float, step: float) -> float:
        if step <= 0:
            raise ValueError("LOT_STEP must be > 0")
        return math.floor((value + 1e-12) / step) * step

    def _lot_for_order(self, order: dict[str, Any]) -> tuple[float, float]:
        account = self.paper.account()
        equity = float(account["balance"])
        risk_usd = equity * float(settings.trend_risk_percent)
        loss_per_lot = float(order["risk_distance"]) * float(settings.contract_size)
        if loss_per_lot <= 0:
            raise ValueError("Invalid order risk distance")
        raw_lot = risk_usd / loss_per_lot
        lot = self._round_down(raw_lot, float(settings.lot_step))
        lot = min(lot, float(settings.max_lot))
        return round(lot, 8), risk_usd
