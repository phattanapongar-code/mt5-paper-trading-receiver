from __future__ import annotations

import math
import random
import time
from typing import Any

from app import storage
from app.indicators import compute_indicators
from app.candle_engine import CandleEngine
from app.market_structure import MarketStructureEngine
from app.order_blocks import OrderBlockEngine
from app.multibot.db import default_parameters
from app.backtest.models import BacktestRequest
from app.backtest.report import generate_report


def _round_lot(value: float, step: float, minimum: float, maximum: float) -> float:
    if step <= 0:
        step = 0.01
    rounded = math.floor(value / step) * step
    return round(max(minimum, min(maximum, rounded)), 8)


def _pip_value(symbol: str) -> float:
    s = symbol.upper()
    if "JPY" in s:
        return 0.01
    if "XAU" in s or "XAG" in s:
        return 0.1
    return 0.0001


def _simulate_ticks(candle: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate realistic ticks from M1 OHLC using tick_count for volume weighting."""
    num_ticks = max(2, candle.get("tick_count") or 60)
    o = float(candle["open"])
    c = float(candle["close"])
    h = float(candle["high"])
    l = float(candle["low"])
    sym = candle["symbol"]
    open_ts = int(candle["open_time"])
    close_ts = int(candle["close_time"])
    duration = max(1, close_ts - open_ts)

    ticks = []
    for i in range(num_ticks):
        progress = (i + 1) / num_ticks
        base = o + (c - o) * progress
        noise = random.uniform(-1, 1) * (h - l) * 0.2
        price = max(l, min(h, base + noise))
        spread = random.uniform(0.3, 0.8)
        mid = price
        ts = open_ts + int(duration * progress)
        ticks.append({
            "type": "tick",
            "symbol": sym,
            "bid": round(mid - spread / 2, 2),
            "ask": round(mid + spread / 2, 2),
            "timestamp": ts,
            "seq": i,
        })
    return ticks


class BacktestEngine:
    def __init__(self, config: BacktestRequest):
        self.config = config
        self.balance = config.initial_balance
        self.peak_equity = config.initial_balance
        self.max_dd = 0.0
        self.trades: list[dict[str, Any]] = []
        self.equity_curve: list[dict[str, Any]] = []
        self.position: dict[str, Any] | None = None
        self.pending: dict[str, Any] | None = None
        self.consecutive_losses = 0
        self.daily_pnl = 0.0
        self.trading_day = ""
        self.params = default_parameters()
        self.params.update(config.parameters)

        # In-memory engines
        self.candle_engine = CandleEngine()
        self.structure = MarketStructureEngine()
        self.order_blocks = OrderBlockEngine()

        # Load visual strategy graph
        self.graph = self._load_graph()

    def _load_graph(self) -> dict[str, Any] | None:
        """Load visual strategy graph from visual_strategy_id or inline graph."""
        import json
        if self.config.visual_strategy_id:
            row = storage.query_one(
                "SELECT graph_json FROM visual_strategies WHERE id=?",
                (self.config.visual_strategy_id,),
            )
            if row:
                return json.loads(row["graph_json"])
        return self.config.graph

    def run(self) -> dict[str, Any]:
        now_ts = int(time.time())

        # Load M1 candles
        rows = storage.query_all(
            "SELECT * FROM candles WHERE symbol=? AND timeframe='M1' AND is_closed=1 AND open_time BETWEEN ? AND ? ORDER BY open_time ASC",
            (self.config.symbol, self.config.start_time, self.config.end_time),
        )
        if not rows:
            return {"ok": False, "error": "No M1 candles found in date range"}

        # Pre-build M1 candle engine from history
        for candle in rows:
            self.candle_engine.update_tick(
                candle["symbol"], float(candle["open"]), float(candle["open"]), int(candle["open_time"])
            )

        # Walk through candles
        for candle in rows:
            ts = int(candle["open_time"])
            ticks = _simulate_ticks(candle)

            for tick in ticks:
                self._process_tick(tick, ts)

        # Close any remaining position
        if self.position:
            last_price = (float(rows[-1]["high"]) + float(rows[-1]["low"])) / 2
            self._close_position(last_price, "end_of_test", int(rows[-1]["close_time"]))
            self.position = None

        return generate_report(self.trades, self.equity_curve, self.config.initial_balance)

    def _process_tick(self, tick: dict[str, Any], now: int) -> None:
        symbol = tick["symbol"]
        bid = float(tick["bid"])
        ask = float(tick["ask"])

        # Feed candle engine
        result = self.candle_engine.update_tick(symbol, bid, ask, now)
        closed = result.get("closed", [])

        # Refresh structure and OBs when timeframes close
        if closed:
            tf_list = [c["timeframe"] for c in closed]
            self.structure.refresh_timeframes(symbol, tf_list)
            self.order_blocks.refresh_timeframes(symbol, tf_list)

        # Record equity
        eq = self.balance + (self._position_unrealized_pnl(bid, ask) if self.position else 0)
        if eq > self.peak_equity:
            self.peak_equity = eq
        dd = (self.peak_equity - eq) / self.peak_equity if self.peak_equity > 0 else 0
        if dd > self.max_dd:
            self.max_dd = dd
        self.equity_curve.append({"time": now, "equity": round(eq, 2)})

        # Evaluate bot
        self._evaluate_tick(tick, now)

    def _position_unrealized_pnl(self, bid: float, ask: float) -> float:
        if not self.position:
            return 0.0
        price = bid if self.position["side"] == "buy" else ask
        direction = 1.0 if self.position["side"] == "buy" else -1.0
        entry = float(self.position["entry"])
        lot = float(self.position["lot"])
        contract = float(self.params["contract_size"])
        return (price - entry) * direction * lot * contract

    def _close_position(self, exit_price: float, reason: str, now: int) -> None:
        if not self.position:
            return
        pos = self.position
        side = str(pos["side"])
        direction = 1.0 if side == "buy" else -1.0
        contract = float(self.params["contract_size"])
        pnl = (exit_price - float(pos["entry"])) * direction * float(pos["lot"]) * contract
        risk = abs(float(pos["entry"]) - float(pos.get("stop_loss") or pos["entry"])) * float(pos["lot"]) * contract
        r_multiple = pnl / risk if risk > 0 else 0.0
        self.balance += pnl
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        self.trades.append({
            "id": len(self.trades) + 1,
            "symbol": pos.get("symbol", self.config.symbol),
            "side": side,
            "lot": float(pos["lot"]),
            "entry": float(pos["entry"]),
            "exit": exit_price,
            "stop_loss": float(pos.get("stop_loss", 0)),
            "take_profit": float(pos.get("take_profit", 0)),
            "pnl": round(pnl, 2),
            "r_multiple": round(r_multiple, 2),
            "exit_reason": reason,
            "opened_at": pos.get("opened_at", now),
            "closed_at": now,
        })
        self.position = None

    def _evaluate_tick(self, tick: dict[str, Any], now: int) -> None:
        if not self.graph:
            return
        bid = float(tick["bid"])
        ask = float(tick["ask"])

        # Check position SL/TP
        if self.position:
            p = self.position
            if p["side"] == "buy":
                if p.get("stop_loss") and bid <= float(p["stop_loss"]):
                    self._close_position(bid, "sl_hit", now)
                    return
                if p.get("take_profit") and bid >= float(p["take_profit"]):
                    self._close_position(bid, "tp_hit", now)
                    return
            else:
                if p.get("stop_loss") and ask >= float(p["stop_loss"]):
                    self._close_position(ask, "sl_hit", now)
                    return
                if p.get("take_profit") and ask <= float(p["take_profit"]):
                    self._close_position(ask, "tp_hit", now), now
                    return
            # Trailing stop (simplified)
            if self.params.get("trailing_enabled") and p.get("stop_loss"):
                activate = float(self.params.get("trail_activation_pips", 10))
                trail = float(self.params.get("trail_distance_pips", 5))
                step = float(self.params.get("trail_step_pips", 1))
                pip_val = _pip_value(self.config.symbol)
                if p["side"] == "buy":
                    diff = bid - float(p["entry"])
                    if diff >= activate * pip_val:
                        new_sl = bid - trail * pip_val
                        old_sl = float(p["stop_loss"])
                        if new_sl > old_sl + step * pip_val:
                            p["stop_loss"] = new_sl
                else:
                    diff = float(p["entry"]) - ask
                    if diff >= activate * pip_val:
                        new_sl = ask + trail * pip_val
                        old_sl = float(p["stop_loss"])
                        if new_sl < old_sl - step * pip_val:
                            p["stop_loss"] = new_sl
            return

        # Check pending order fill
        if self.pending:
            po = self.pending
            if po.get("expires_at") and now >= int(po["expires_at"]):
                self.pending = None
                return
            should_fill = (po["side"] == "buy" and ask <= float(po["entry"])) or (po["side"] == "sell" and bid >= float(po["entry"]))
            if should_fill:
                fill_price = ask if po["side"] == "buy" else bid
                self.position = {
                    "symbol": po["symbol"], "side": po["side"], "lot": po["lot"],
                    "entry": fill_price, "stop_loss": po["stop_loss"],
                    "take_profit": po["take_profit"], "opened_at": now,
                }
                self.pending = None
            return

        # Risk gates
        spread = ask - bid
        if spread > float(self.params.get("max_spread", 1.5)):
            return
        daily_limit = self.config.initial_balance * float(self.params.get("daily_loss_limit_percent", 0.03))
        # Simplified: reset daily at midnight of each day in the backtest
        day_str = str(now)
        if self.daily_pnl <= -daily_limit:
            return
        if self.consecutive_losses >= int(self.params.get("max_consecutive_losses", 3)):
            return

        # Build mock bot for visual strategy (needed by get_visual_graph)
        bot = {
            "id": 0,
            "symbol": self.config.symbol,
            "timeframe": self.config.timeframe,
            "parameters_json": "",
        }

        from app.multibot.visual_engine import execute_graph
        decision = execute_graph(
            self.graph,
            bid=bid,
            ask=ask,
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
        )
        if decision is None:
            return
        action = str(decision.get("action", "")).lower()
        if action not in ("buy", "sell"):
            return
        entry = float(decision["entry"])
        sl = float(decision["stop_loss"])
        tp = float(decision["take_profit"])
        risk_dist = abs(entry - sl)
        if risk_dist <= 0:
            return
        rr = float(decision.get("risk_reward", 0) or (abs(tp - entry) / risk_dist))
        if rr < 1.5:
            return
        risk_usd = self.balance * float(self.params.get("risk_percent", 0.01))
        lot = _round_lot(
            risk_usd / (risk_dist * float(self.params.get("contract_size", 100))),
            float(self.params.get("lot_step", 0.01)),
            float(self.params.get("min_lot", 0.01)),
            float(self.params.get("max_lot", 10)),
        )
        if lot <= 0:
            return
        expiry = int(self.params.get("expiry_candles", 8)) * 900
        self.pending = {
            "symbol": self.config.symbol,
            "side": action,
            "entry": entry,
            "stop_loss": sl,
            "take_profit": tp,
            "lot": lot,
            "risk_reward": rr,
            "expires_at": now + expiry,
            "ob_key": decision.get("ob_key", f"bt:{now}"),
        }
