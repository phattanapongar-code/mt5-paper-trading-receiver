from __future__ import annotations

import asyncio
import json
import math
import time
from datetime import datetime, timezone
from typing import Any

from app import storage
from app.indicators import compute_indicators
from app.multibot.db import default_parameters, json_text


def _params(raw: str | None) -> dict[str, Any]:
    p = default_parameters()
    try:
        p.update(json.loads(raw or "{}"))
    except Exception:
        pass
    return p


def _log(conn, bot_id: int, event_type: str, message: str, payload: dict[str, Any] | None = None) -> None:
    conn.execute(
        "INSERT INTO bot_signal_logs(bot_id,event_type,message,payload_json,created_at) VALUES(?,?,?,?,?)",
        (bot_id, event_type, message, json_text(payload or {}), int(time.time())),
    )


def _trend(symbol: str, timeframe: str) -> str:
    if not storage.table_exists("candles"):
        return "WARMING_UP"
    rows = storage.query_all(
        "SELECT open, high, low, close, is_closed FROM candles WHERE symbol=? AND timeframe=? AND is_closed=1 ORDER BY open_time DESC LIMIT 300",
        (symbol, timeframe),
    )
    if not rows:
        return "WARMING_UP"
    candles = list(reversed(rows))
    result = compute_indicators(candles)
    return str(result["trend"])


def _m5_confirmed(symbol: str, side: str) -> bool:
    if not storage.table_exists("bos_events"):
        return True
    row = storage.query_one("SELECT side FROM bos_events WHERE symbol=? AND timeframe='M5' ORDER BY break_open_time DESC LIMIT 1", (symbol,))
    return row is not None and str(row["side"]).lower() == side.lower()


def _latest_ob(symbol: str, timeframe: str, min_score: int, allow_tested_once: bool) -> dict[str, Any] | None:
    if not storage.table_exists("order_blocks"):
        return None
    ob_cols = storage.columns("order_blocks")
    required = {"symbol", "timeframe", "side", "ob_low", "ob_high", "status", "score", "is_strong"}
    if not required.issubset(ob_cols):
        return None
    statuses = ["active"] + (["tested_once"] if allow_tested_once else [])
    placeholders = ",".join("?" for _ in statuses)
    order_col = "break_open_time" if "break_open_time" in ob_cols else "id"
    return storage.query_one(
        f"""
        SELECT * FROM order_blocks
        WHERE symbol=? AND timeframe=? AND is_strong=1 AND score>=? AND status IN ({placeholders})
        ORDER BY {order_col} DESC, id DESC LIMIT 1
        """,
        (symbol, timeframe, min_score, *statuses),
    )


def _stable_ob_key(ob: dict[str, Any]) -> str:
    return ":".join(str(ob.get(k, "")) for k in ("symbol", "timeframe", "side", "break_open_time", "ob_open_time"))


def _round_lot(value: float, step: float, minimum: float, maximum: float) -> float:
    if step <= 0:
        step = 0.01
    rounded = math.floor(value / step) * step
    return round(max(minimum, min(maximum, rounded)), 8)


def _close_position(conn, position: dict[str, Any], exit_price: float, reason: str, now: int) -> None:
    side = str(position["side"]).lower()
    direction = 1.0 if side == "buy" else -1.0
    contract_size = float(_params(None)["contract_size"])
    pnl = (exit_price - float(position["entry"])) * direction * float(position["lot"]) * contract_size
    risk = abs(float(position["entry"]) - float(position["stop_loss"] or position["entry"])) * float(position["lot"]) * contract_size
    r_multiple = pnl / risk if risk > 0 else 0.0
    conn.execute(
        "UPDATE bot_positions SET status='closed',closed_at=?,exit_price=?,pnl=?,r_multiple=?,exit_reason=?,updated_at=? WHERE id=?",
        (now, exit_price, pnl, r_multiple, reason, now, position["id"]),
    )
    wallet = conn.execute("SELECT * FROM wallets WHERE id=?", (position["wallet_id"],)).fetchone()
    new_balance = float(wallet["balance"]) + pnl
    peak = max(float(wallet["peak_equity"]), new_balance)
    drawdown = ((peak - new_balance) / peak) if peak > 0 else 0.0
    max_dd = max(float(wallet["max_drawdown"]), drawdown)
    conn.execute(
        "UPDATE wallets SET balance=?,realized_pnl=realized_pnl+?,peak_equity=?,max_drawdown=?,updated_at=? WHERE id=?",
        (new_balance, pnl, peak, max_dd, now, wallet["id"]),
    )
    state = conn.execute("SELECT * FROM bot_runtime_state WHERE bot_id=?", (position["bot_id"],)).fetchone()
    losses = int(state["consecutive_losses"] or 0) if state else 0
    losses = losses + 1 if pnl < 0 else 0
    day = datetime.now(timezone.utc).date().isoformat()
    daily = float(state["daily_realized_pnl"] or 0.0) if state and state["trading_day"] == day else 0.0
    daily += pnl
    conn.execute(
        "UPDATE bot_runtime_state SET consecutive_losses=?,daily_realized_pnl=?,trading_day=?,updated_at=? WHERE bot_id=?",
        (losses, daily, day, now, position["bot_id"]),
    )
    _log(conn, position["bot_id"], "position_closed", reason, {"position_id": position["id"], "pnl": pnl, "r_multiple": r_multiple})


def _evaluate_bot(conn, bot: dict[str, Any], tick: dict[str, Any], now: int) -> None:
    bot_id = int(bot["id"])
    wallet_id = int(bot["wallet_id"])
    params = _params(bot.get("parameters_json"))
    bid, ask = float(tick["bid"]), float(tick["ask"])
    spread = ask - bid
    trend = _trend(bot["symbol"], bot["timeframe"])
    day = datetime.now(timezone.utc).date().isoformat()
    conn.execute("INSERT OR IGNORE INTO bot_runtime_state(bot_id,updated_at) VALUES(?,?)", (bot_id, now))
    state = conn.execute("SELECT * FROM bot_runtime_state WHERE bot_id=?", (bot_id,)).fetchone()
    if state and state["trading_day"] != day:
        conn.execute("UPDATE bot_runtime_state SET daily_realized_pnl=0,trading_day=?,paused_reason=NULL,updated_at=? WHERE bot_id=?", (day, now, bot_id))
        state = conn.execute("SELECT * FROM bot_runtime_state WHERE bot_id=?", (bot_id,)).fetchone()
    conn.execute("UPDATE bot_runtime_state SET latest_tick_json=?,latest_trend=?,updated_at=? WHERE bot_id=?", (json_text(tick), trend, now, bot_id))

    position = conn.execute("SELECT * FROM bot_positions WHERE bot_id=? AND status='open' ORDER BY id DESC LIMIT 1", (bot_id,)).fetchone()
    if position:
        p = dict(position)
        if p["side"] == "buy":
            if p["stop_loss"] is not None and bid <= float(p["stop_loss"]):
                _close_position(conn, p, bid, "sl_hit", now)
            elif p["take_profit"] is not None and bid >= float(p["take_profit"]):
                _close_position(conn, p, bid, "tp_hit", now)
        else:
            if p["stop_loss"] is not None and ask >= float(p["stop_loss"]):
                _close_position(conn, p, ask, "sl_hit", now)
            elif p["take_profit"] is not None and ask <= float(p["take_profit"]):
                _close_position(conn, p, ask, "tp_hit", now)
        return

    pending = conn.execute("SELECT * FROM bot_pending_orders WHERE bot_id=? AND status='pending' ORDER BY id DESC LIMIT 1", (bot_id,)).fetchone()
    if pending:
        po = dict(pending)
        if po.get("expires_at") and now >= int(po["expires_at"]):
            conn.execute("UPDATE bot_pending_orders SET status='cancelled',cancel_reason='expired',updated_at=? WHERE id=?", (now, po["id"]))
            _log(conn, bot_id, "pending_cancelled", "expired", {"pending_id": po["id"]})
            return
        should_fill = (po["side"] == "buy" and ask <= float(po["entry"])) or (po["side"] == "sell" and bid >= float(po["entry"]))
        if should_fill:
            fill_price = ask if po["side"] == "buy" else bid
            cur = conn.execute(
                """
                INSERT INTO bot_positions(bot_id,wallet_id,pending_id,symbol,side,lot,entry,stop_loss,take_profit,status,opened_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,'open',?,?)
                """,
                (bot_id, wallet_id, po["id"], po["symbol"], po["side"], po["lot"], fill_price, po["stop_loss"], po["take_profit"], now, now),
            )
            conn.execute("UPDATE bot_pending_orders SET status='filled',filled_at=?,updated_at=? WHERE id=?", (now, now, po["id"]))
            _log(conn, bot_id, "position_opened", "pending_filled", {"pending_id": po["id"], "position_id": cur.lastrowid, "fill_price": fill_price})
        return

    wallet = conn.execute("SELECT * FROM wallets WHERE id=?", (wallet_id,)).fetchone()
    if not wallet:
        return
    if spread > float(params["max_spread"]):
        return
    daily_limit = float(wallet["initial_balance"]) * float(params.get("daily_loss_limit_percent", 0.03))
    if state and float(state["daily_realized_pnl"] or 0.0) <= -daily_limit:
        conn.execute("UPDATE bot_runtime_state SET paused_reason='daily_loss_limit',updated_at=? WHERE bot_id=?", (now, bot_id))
        return
    if state and int(state["consecutive_losses"] or 0) >= int(params.get("max_consecutive_losses", 3)):
        conn.execute("UPDATE bot_runtime_state SET paused_reason='max_consecutive_losses',updated_at=? WHERE bot_id=?", (now, bot_id))
        return

    from app.multibot.strategies import get_strategy
    meta = get_strategy(str(bot.get("strategy_type", "trend_ob")))
    if meta is None:
        _log(conn, bot_id, "strategy_error", f"unknown strategy: {bot.get('strategy_type')}", None)
        return
    decision = meta.decide(conn, bot, tick, params, now)
    if decision is None:
        return
    action = str(decision.get("action", "")).lower()
    if action not in ("buy", "sell"):
        return
    ob_key = decision.get("ob_key")
    if ob_key:
        seen = conn.execute("SELECT 1 FROM bot_pending_orders WHERE bot_id=? AND ob_key=? LIMIT 1", (bot_id, ob_key)).fetchone()
        if seen:
            return
    entry = float(decision["entry"])
    sl = float(decision["stop_loss"])
    tp = float(decision["take_profit"])
    risk_distance = abs(entry - sl)
    if risk_distance <= 0:
        return
    rr = float(decision.get("risk_reward", 0) or (abs(tp - entry) / risk_distance))
    if rr < 1.5:
        return
    risk_usd = float(wallet["balance"]) * float(params["risk_percent"])
    lot = _round_lot(risk_usd / (risk_distance * float(params["contract_size"])), float(params["lot_step"]), float(params["min_lot"]), float(params["max_lot"]))
    if lot <= 0:
        return
    expiry_seconds = int(params["expiry_candles"]) * (900 if bot["timeframe"] == "M15" else 300)
    cur = conn.execute(
        """
        INSERT INTO bot_pending_orders(bot_id,wallet_id,ob_key,symbol,timeframe,side,entry,stop_loss,take_profit,risk_reward,risk_percent,lot,status,created_at,expires_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'pending', ?, ?, ?)
        """,
        (bot_id, wallet_id, ob_key, bot["symbol"], bot["timeframe"], action, entry, sl, tp, rr, params["risk_percent"], lot, now, now + expiry_seconds, now),
    )
    conn.execute("UPDATE bot_runtime_state SET latest_ob_key=?,updated_at=? WHERE bot_id=?", (ob_key, now, bot_id))
    _log(conn, bot_id, "pending_created", str(meta.id), {"pending_id": cur.lastrowid, "ob_key": ob_key, "entry": entry, "sl": sl, "tp": tp, "lot": lot, "strategy": meta.id})


def process_tick_sync(tick: dict[str, Any]) -> dict[str, Any]:
    now = int(time.time())
    processed = 0
    with storage.transaction() as conn:
        rows = conn.execute(
            """
            SELECT b.*,w.id AS wallet_id,w.balance,w.initial_balance
            FROM bots b JOIN profiles p ON p.id=b.profile_id JOIN wallets w ON w.bot_id=b.id
            WHERE b.enabled=1 AND p.enabled=1 AND b.symbol=?
            ORDER BY b.id
            """,
            (tick.get("symbol", "XAUUSD"),),
        ).fetchall()
        for row in rows:
            _evaluate_bot(conn, dict(row), tick, now)
            processed += 1
    return {"ok": True, "processed_bots": processed, "tick": tick}


class RuntimeHub:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[dict[str, Any]] | None = None
        self.worker_task: asyncio.Task | None = None
        self.clients: set[Any] = set()
        self.last_result: dict[str, Any] | None = None
        self.dropped_ticks = 0

    def ensure_started(self) -> None:
        if self.queue is None:
            self.queue = asyncio.Queue(maxsize=1)
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._worker())

    async def submit(self, tick: dict[str, Any]) -> None:
        self.ensure_started()
        assert self.queue is not None
        if self.queue.full():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
                self.dropped_ticks += 1
            except asyncio.QueueEmpty:
                pass
        await self.queue.put(tick)

    async def _worker(self) -> None:
        assert self.queue is not None
        while True:
            tick = await self.queue.get()
            try:
                self.last_result = await asyncio.to_thread(process_tick_sync, tick)
                await self.broadcast({"event": "multibot_state", "runtime": self.status()})
            finally:
                self.queue.task_done()

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead = []
        text = json.dumps(payload, ensure_ascii=False)
        for ws in list(self.clients):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def status(self) -> dict[str, Any]:
        return {
            "running": self.worker_task is not None and not self.worker_task.done(),
            "queue_size": self.queue.qsize() if self.queue else 0,
            "websocket_clients": len(self.clients),
            "dropped_ticks": self.dropped_ticks,
            "last_result": self.last_result,
        }


hub = RuntimeHub()
