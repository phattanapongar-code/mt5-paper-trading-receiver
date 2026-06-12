from __future__ import annotations

import asyncio
import json
import math
import time
from datetime import datetime, timezone
from typing import Any

from app import storage
from app.alert import alert_engine
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


def _pip_value(symbol: str) -> float:
    s = symbol.upper()
    if "JPY" in s:
        return 0.01
    if "XAU" in s or "XAG" in s:
        return 0.1
    return 0.0001


def _trail_stop(conn, position: dict[str, Any], bid: float, ask: float, params: dict[str, Any], now: int) -> None:
    if not params.get("trailing_enabled"):
        return
    activate_pips = float(params.get("trail_activation_pips", 10))
    trail_dist = float(params.get("trail_distance_pips", 5))
    step_pips = float(params.get("trail_step_pips", 1))
    pip_val = _pip_value(str(position.get("symbol", "XAUUSD")))
    entry = float(position["entry"])
    if position["side"] == "buy":
        price_diff = bid - entry
        if price_diff >= activate_pips * pip_val:
            new_sl = bid - trail_dist * pip_val
            old_sl = float(position["stop_loss"] or 0)
            if new_sl > old_sl + step_pips * pip_val:
                conn.execute("UPDATE bot_positions SET stop_loss=?,updated_at=? WHERE id=?", (new_sl, now, position["id"]))
    else:
        price_diff = entry - ask
        if price_diff >= activate_pips * pip_val:
            new_sl = ask + trail_dist * pip_val
            old_sl = float(position["stop_loss"] or 0)
            if new_sl < old_sl - step_pips * pip_val:
                conn.execute("UPDATE bot_positions SET stop_loss=?,updated_at=? WHERE id=?", (new_sl, now, position["id"]))


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
    alert_engine.notify_trade_close(str(position.get("bot_name", "?")), side, pnl, reason, str(position.get("symbol", "?")), r_multiple)
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
        # Trailing stop: move SL toward price after position still open
        _trail_stop(conn, p, bid, ask, params, now)
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
            alert_engine.notify_trade_open(bot.get("name", "?"), str(po["side"]), fill_price, float(po["stop_loss"]), float(po["take_profit"]), float(po["lot"]), str(po["symbol"]))
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


def _log_safe(conn_eval, bot_id: int, msg: str, exception: Exception) -> None:
    try:
        _log(conn_eval, bot_id, "eval_error", msg, {"error": str(exception)})
    except Exception:
        pass


def process_tick_sync(tick: dict[str, Any]) -> dict[str, Any]:
    now = int(time.time())
    processed = 0
    errors: list[dict[str, Any]] = []
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
            bot = dict(row)
            try:
                conn.execute(f"SAVEPOINT bot_{bot['id']}")
                _evaluate_bot(conn, bot, tick, now)
                conn.execute(f"RELEASE bot_{bot['id']}")
                processed += 1
            except Exception as exc:
                try:
                    conn.execute(f"ROLLBACK TO bot_{bot['id']}")
                except Exception:
                    pass
                alert_engine.notify_error(bot.get("name", "?"), str(exc))
                _log_safe(conn, bot["id"], f"eval_error [{bot.get('strategy_type','?')}]", exc)
                errors.append({"bot_id": bot["id"], "error": str(exc)})
    result: dict[str, Any] = {"ok": True, "processed_bots": processed, "tick": tick}
    if errors:
        result["errors"] = errors
    return result


class RuntimeHub:
    def __init__(self) -> None:
        self.clients: set[Any] = set()
        self.last_result: dict[str, Any] | None = None

    async def broadcast(self, payload: dict[str, Any]) -> None:
        if not self.clients:
            return
        dead: list[Any] = []
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
            "websocket_clients": len(self.clients),
            "last_result": self.last_result,
        }

    def set_result(self, result: dict[str, Any]) -> None:
        self.last_result = result
        self._maybe_broadcast()

    def _maybe_broadcast(self) -> None:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.broadcast({"event": "multibot_state", "runtime": self.status()}))
        except RuntimeError:
            pass


hub = RuntimeHub()
