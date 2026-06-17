from __future__ import annotations

import json
import math
import random
import time
from typing import Any

from app import storage
from app.alert import alert_engine
from app.config import settings
from app.multibot.db import default_parameters, json_text


def _decode(value: str | None) -> dict[str, Any]:
    try:
        return json.loads(value or "{}")
    except Exception:
        return {}


# ── Execution Realism Helpers (shared with runtime) ──

def _gaussian_slippage(sigma_pips: float, max_pips: float) -> float:
    raw = random.gauss(0, sigma_pips)
    return round(max(-max_pips, min(max_pips, raw)), 4)


def _pip_value(symbol: str) -> float:
    s = symbol.upper()
    if "JPY" in s:
        return 0.01
    if "XAU" in s or "XAG" in s:
        return 0.1
    return 0.0001


def _apply_exit_slippage(price: float, side: str, slippage_pts: float) -> float:
    if slippage_pts == 0:
        return price
    if side == "buy":
        return price - abs(slippage_pts)
    return price + abs(slippage_pts)


def _apply_entry_slippage(price: float, side: str, slippage_pts: float) -> float:
    if slippage_pts == 0:
        return price
    if side == "buy":
        return price + abs(slippage_pts)
    return price - abs(slippage_pts)


def _compute_commission(lot: float, entry_price: float, contract_size: float, params: dict[str, Any]) -> float:
    comm_type = str(params.get("commission_type", "fixed"))
    if comm_type == "percentage":
        return round(lot * contract_size * entry_price * float(params.get("commission_pct", 0)), 2)
    return round(lot * float(params.get("commission_per_lot", 0)), 2)


def list_profiles() -> list[dict[str, Any]]:
    return storage.query_all(
        """
        SELECT p.*, COUNT(b.id) AS bot_count,
               COALESCE(SUM(w.balance),0) AS total_balance,
               COALESCE(SUM(w.realized_pnl),0) AS total_realized_pnl
        FROM profiles p
        LEFT JOIN bots b ON b.profile_id=p.id
        LEFT JOIN wallets w ON w.bot_id=b.id
        GROUP BY p.id ORDER BY p.id
        """
    )


def create_profile(name: str, description: str = "", enabled: bool = True) -> dict[str, Any]:
    now = int(time.time())
    with storage.transaction() as conn:
        cur = conn.execute(
            "INSERT INTO profiles(name, description, enabled, created_at, updated_at) VALUES(?,?,?,?,?)",
            (name, description, 1 if enabled else 0, now, now),
        )
        return dict(conn.execute("SELECT * FROM profiles WHERE id=?", (cur.lastrowid,)).fetchone())


def set_profile_enabled(profile_id: int, enabled: bool) -> dict[str, Any] | None:
    storage.execute("UPDATE profiles SET enabled=?, updated_at=? WHERE id=?", (1 if enabled else 0, int(time.time()), profile_id))
    return storage.query_one("SELECT * FROM profiles WHERE id=?", (profile_id,))


def list_bots(profile_id: int | None = None) -> list[dict[str, Any]]:
    where = "WHERE b.profile_id=?" if profile_id is not None else ""
    params = (profile_id,) if profile_id is not None else ()
    rows = storage.query_all(
        f"""
        SELECT b.*, p.name AS profile_name, p.enabled AS profile_enabled,
               w.id AS wallet_id, w.initial_balance, w.balance, w.realized_pnl,
               w.currency, w.max_drawdown, w.peak_equity,
               w.total_commission, w.total_spread_cost, w.total_slippage,
               COALESCE((SELECT COUNT(*) FROM bot_pending_orders x WHERE x.bot_id=b.id AND x.status='pending'),0) AS pending_count,
               COALESCE((SELECT COUNT(*) FROM bot_positions x WHERE x.bot_id=b.id AND x.status='open'),0) AS open_position_count,
               s.latest_trend, s.paused_reason, s.updated_at AS runtime_updated_at
        FROM bots b
        JOIN profiles p ON p.id=b.profile_id
        JOIN wallets w ON w.bot_id=b.id
        LEFT JOIN bot_runtime_state s ON s.bot_id=b.id
        {where}
        ORDER BY b.id
        """,
        params,
    )
    out = []
    for item in rows:
        item["parameters"] = _decode(item.pop("parameters_json", "{}"))
        out.append(item)
    return out


def get_bot(bot_id: int) -> dict[str, Any] | None:
    bots = [b for b in list_bots() if b["id"] == bot_id]
    return bots[0] if bots else None


def create_bot(profile_id: int, name: str, visual_strategy_id: int | None = None,
               symbol: str = "XAUUSD", timeframe: str = "M15", enabled: bool = False,
               initial_balance: float = 500.0, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    now = int(time.time())
    params = default_parameters()
    params.update(parameters or {})
    with storage.transaction() as conn:
        cur = conn.execute(
            """
            INSERT INTO bots(profile_id,name,strategy_type,strategy_version,symbol,timeframe,enabled,parameters_json,visual_strategy_id,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (profile_id, name, "visual", "v1", symbol, timeframe, 1 if enabled else 0, json_text(params), visual_strategy_id, now, now),
        )
        bot_id = cur.lastrowid
        conn.execute(
            "INSERT INTO wallets(bot_id,initial_balance,balance,realized_pnl,peak_equity,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (bot_id, initial_balance, initial_balance, 0.0, initial_balance, now, now),
        )
        conn.execute("INSERT INTO bot_runtime_state(bot_id, updated_at) VALUES(?,?)", (bot_id, now))
    return get_bot(bot_id) or {}


def clone_bot(bot_id: int, name: str) -> dict[str, Any]:
    source = get_bot(bot_id)
    if source is None:
        raise ValueError("bot not found")
    return create_bot(source["profile_id"], name, source.get("visual_strategy_id"), source["symbol"], source["timeframe"], False, source["initial_balance"], source["parameters"])


def set_bot_enabled(bot_id: int, enabled: bool) -> dict[str, Any] | None:
    storage.execute("UPDATE bots SET enabled=?, updated_at=? WHERE id=?", (1 if enabled else 0, int(time.time()), bot_id))
    return get_bot(bot_id)


def update_bot_parameters(bot_id: int, parameters: dict[str, Any]) -> dict[str, Any] | None:
    bot = get_bot(bot_id)
    if bot is None:
        return None
    merged = default_parameters()
    merged.update(bot.get("parameters") or {})
    merged.update(parameters)
    storage.execute("UPDATE bots SET parameters_json=?, updated_at=? WHERE id=?", (json_text(merged), int(time.time()), bot_id))
    return get_bot(bot_id)


def get_wallet(bot_id: int) -> dict[str, Any] | None:
    return storage.query_one("SELECT * FROM wallets WHERE bot_id=?", (bot_id,))


def reset_wallet(bot_id: int, balance: float) -> dict[str, Any] | None:
    now = int(time.time())
    with storage.transaction() as conn:
        wallet = conn.execute("SELECT id FROM wallets WHERE bot_id=?", (bot_id,)).fetchone()
        if wallet is None:
            return None
        conn.execute("DELETE FROM bot_pending_orders WHERE bot_id=?", (bot_id,))
        conn.execute("DELETE FROM bot_positions WHERE bot_id=?", (bot_id,))
        conn.execute("UPDATE wallets SET initial_balance=?, balance=?, realized_pnl=0, max_drawdown=0, peak_equity=?, total_commission=0, total_spread_cost=0, total_slippage=0, updated_at=? WHERE bot_id=?", (balance, balance, balance, now, bot_id))
        conn.execute("UPDATE bot_runtime_state SET consecutive_losses=0,daily_realized_pnl=0,paused_reason=NULL,updated_at=? WHERE bot_id=?", (now, bot_id))
        result = dict(conn.execute("SELECT * FROM wallets WHERE bot_id=?", (bot_id,)).fetchone())
    return result


def compare(bot_ids: list[int] | None = None) -> list[dict[str, Any]]:
    where = ""
    params: list[Any] = []
    if bot_ids:
        where = f" WHERE b.id IN ({','.join('?' for _ in bot_ids)})"
        params = list(bot_ids)
    rows = storage.query_all(
        f"""
        SELECT b.id AS bot_id, b.name, p.name AS profile_name, b.strategy_type, b.strategy_version,
               b.symbol, b.timeframe, b.visual_strategy_id,
               w.initial_balance, w.balance, w.realized_pnl, w.max_drawdown,
               w.total_commission, w.total_spread_cost, w.total_slippage,
               (SELECT COUNT(*) FROM bot_positions bp WHERE bp.bot_id=b.id AND bp.status='closed') AS closed_trades,
               (SELECT COUNT(*) FROM bot_positions bp WHERE bp.bot_id=b.id AND bp.status='open') AS open_positions,
               (SELECT COUNT(*) FROM bot_pending_orders po WHERE po.bot_id=b.id AND po.status='pending') AS pending_orders,
               (SELECT COUNT(*) FROM bot_positions bp WHERE bp.bot_id=b.id AND bp.status='closed' AND COALESCE(bp.net_pnl,bp.pnl)>0) AS wins,
               (SELECT COALESCE(SUM(COALESCE(bp.net_pnl,bp.pnl)),0) FROM bot_positions bp WHERE bp.bot_id=b.id AND bp.status='closed') AS net_pnl
        FROM bots b JOIN profiles p ON p.id=b.profile_id JOIN wallets w ON w.bot_id=b.id
        {where} ORDER BY b.id
        """,
        params,
    )
    out = []
    for item in rows:
        item["win_rate"] = (item["wins"] / item["closed_trades"] * 100.0) if item["closed_trades"] else 0.0
        out.append(item)
    return out


def bot_state(bot_id: int) -> dict[str, Any] | None:
    bot = get_bot(bot_id)
    if not bot:
        return None
    pending = storage.query_one("SELECT * FROM bot_pending_orders WHERE bot_id=? AND status='pending' ORDER BY id DESC LIMIT 1", (bot_id,))
    position = storage.query_one("SELECT *, exit_price AS \"exit\" FROM bot_positions WHERE bot_id=? AND status='open' ORDER BY id DESC LIMIT 1", (bot_id,))
    state = storage.query_one("SELECT * FROM bot_runtime_state WHERE bot_id=?", (bot_id,))
    trades = storage.query_all("SELECT *, exit_price AS \"exit\" FROM bot_positions WHERE bot_id=? ORDER BY id DESC LIMIT 20", (bot_id,))
    return {"bot": bot, "pending": pending, "position": position, "runtime": state, "trades": trades}


def signal_logs(bot_id: int, limit: int = 100) -> list[dict[str, Any]]:
    return storage.query_all("SELECT * FROM bot_signal_logs WHERE bot_id=? ORDER BY id DESC LIMIT ?", (bot_id, limit))


def trades(bot_id: int, limit: int = 100) -> list[dict[str, Any]]:
    return storage.query_all("SELECT *, exit_price AS \"exit\" FROM bot_positions WHERE bot_id=? ORDER BY id DESC LIMIT ?", (bot_id, limit))


def delete_profile(profile_id: int) -> bool:
    with storage.transaction() as conn:
        bot_ids = [r[0] for r in conn.execute("SELECT id FROM bots WHERE profile_id=?", (profile_id,)).fetchall()]
        for bid in bot_ids:
            conn.execute("DELETE FROM bot_pending_orders WHERE bot_id=?", (bid,))
            conn.execute("DELETE FROM bot_positions WHERE bot_id=?", (bid,))
            conn.execute("DELETE FROM bot_signal_logs WHERE bot_id=?", (bid,))
            conn.execute("DELETE FROM bot_runtime_state WHERE bot_id=?", (bid,))
            conn.execute("DELETE FROM wallets WHERE bot_id=?", (bid,))
        conn.execute("DELETE FROM bots WHERE profile_id=?", (profile_id,))
        conn.execute("DELETE FROM profiles WHERE id=?", (profile_id,))
    return True


def rename_bot(bot_id: int, name: str) -> dict[str, Any] | None:
    bot = get_bot(bot_id)
    if bot is None:
        return None
    storage.execute("UPDATE bots SET name=?, updated_at=? WHERE id=?", (name, int(time.time()), bot_id))
    return get_bot(bot_id)


def update_bot(bot_id: int, **updates) -> dict[str, Any] | None:
    bot = get_bot(bot_id)
    if bot is None:
        return None
    now = int(time.time())
    with storage.transaction() as conn:
        pairs = []
        params: list[Any] = []
        for key in ("name", "symbol", "timeframe", "enabled", "visual_strategy_id"):
            if key in updates and updates[key] is not None:
                pairs.append(f"{key}=?")
                if key == "enabled":
                    val = 1 if updates[key] else 0
                else:
                    val = updates[key]
                params.append(val)
        if pairs:
            params.append(now)
            params.append(bot_id)
            conn.execute(f"UPDATE bots SET {', '.join(pairs)}, updated_at=? WHERE id=?", params)

        if "initial_balance" in updates and updates["initial_balance"] is not None:
            bal = updates["initial_balance"]
            conn.execute("DELETE FROM bot_pending_orders WHERE bot_id=?", (bot_id,))
            conn.execute("DELETE FROM bot_positions WHERE bot_id=?", (bot_id,))
            conn.execute("UPDATE wallets SET initial_balance=?, balance=?, realized_pnl=0, max_drawdown=0, peak_equity=?, updated_at=? WHERE bot_id=?", (bal, bal, bal, now, bot_id))
            conn.execute("UPDATE bot_runtime_state SET consecutive_losses=0,daily_realized_pnl=0,paused_reason=NULL,updated_at=? WHERE bot_id=?", (now, bot_id))
    return get_bot(bot_id)


def open_position(bot_id: int, side: str, lot: float, stop_loss: float | None, take_profit: float | None, tick: dict[str, Any]) -> dict[str, Any] | None:
    """Open a manual position for a specific bot."""
    bot = get_bot(bot_id)
    if bot is None:
        return None
    wallet = get_wallet(bot_id)
    if wallet is None:
        return None
    params = _decode(bot.get("parameters_json", "{}"))
    sym = str(bot.get("symbol", "XAUUSD"))
    sigma = float(params.get("slippage_sigma", 0.15))
    max_slip = float(params.get("slippage_max_pips", 0.5))
    pip_val = _pip_value(sym)
    slip_pips = _gaussian_slippage(sigma, max_slip)
    slip_pts = slip_pips * pip_val

    # Look up bid/ask for the bot's symbol (not from passed tick, which may be wrong symbol)
    with storage.transaction() as conn:
        tick_row = conn.execute(
            "SELECT bid, ask FROM ticks WHERE symbol=? ORDER BY ts DESC LIMIT 1",
            (sym,),
        ).fetchone()
        if tick_row:
            bid = float(tick_row["bid"])
            ask = float(tick_row["ask"])
        else:
            bid = float(tick.get("bid", 0))
            ask = float(tick.get("ask", 0))
        raw_entry = ask if side == "buy" else bid
    entry = _apply_entry_slippage(raw_entry, side, slip_pts)
    now = int(time.time())
    with storage.transaction() as conn:
        existing = conn.execute("SELECT id FROM bot_positions WHERE bot_id=? AND status='open' LIMIT 1", (bot_id,)).fetchone()
        if existing:
            raise ValueError("Only one open position is allowed")
        cur = conn.execute(
            """
            INSERT INTO bot_positions(bot_id,wallet_id,symbol,side,lot,entry,stop_loss,take_profit,status,opened_at,updated_at,execution_detail)
            VALUES(?,?,?,?,?,?,?,?,'open',?,?,?)
            """,
            (bot_id, wallet["id"], sym, side, lot, entry, stop_loss, take_profit, now, now,
             json_text({"entry_slippage_pips": slip_pips, "fill_price_raw": raw_entry})),
        )
        pos = dict(conn.execute("SELECT *, exit_price AS \"exit\" FROM bot_positions WHERE id=?", (cur.lastrowid,)).fetchone())
        alert_engine.notify_trade_open(
            str(bot.get("name", "?")), side, entry, stop_loss or 0, take_profit or 0, lot,
            sym, slippage_pips=slip_pips, source="manual", bot_id=bot_id,
        )
        return pos


def close_position(bot_id: int, tick: dict[str, Any], note: str = "manual_close") -> dict[str, Any] | None:
    """Close the open position for a specific bot."""
    from app.config import settings
    with storage.transaction() as conn:
        position = conn.execute("SELECT * FROM bot_positions WHERE bot_id=? AND status='open' ORDER BY id DESC LIMIT 1", (bot_id,)).fetchone()
        if position is None:
            raise ValueError("No open position")
        p = dict(position)
        bot_row = conn.execute("SELECT parameters_json, name FROM bots WHERE id=?", (bot_id,)).fetchone()
        params = _decode(bot_row["parameters_json"] if bot_row else "{}")
        bot_name = str(bot_row["name"]) if bot_row else "?"

        # Get current bid/ask for the position's symbol (not from passed tick, which may be wrong symbol)
        sym = str(p.get("symbol", "XAUUSD"))
        tick_row = conn.execute(
            "SELECT bid, ask FROM ticks WHERE symbol=? ORDER BY ts DESC LIMIT 1",
            (sym,),
        ).fetchone()
        if tick_row:
            bid = float(tick_row["bid"])
            ask = float(tick_row["ask"])
        else:
            bid = float(tick.get("bid", 0))
            ask = float(tick.get("ask", 0))
        side = str(p["side"])
        contract_size = float(params.get("contract_size", settings.contract_size))

        # Compute exit slippage
        sigma = float(params.get("slippage_sigma", 0.15))
        max_slip = float(params.get("slippage_max_pips", 0.5))
        pip_val = _pip_value(sym)
        slip_pips = _gaussian_slippage(sigma, max_slip)
        slip_pts = slip_pips * pip_val
        raw_exit = bid if side == "buy" else ask
        exit_price = _apply_exit_slippage(raw_exit, side, slip_pts)

        direction = 1.0 if side == "buy" else -1.0
        pnl = (exit_price - float(p["entry"])) * direction * float(p["lot"]) * contract_size
        risk = abs(float(p["entry"]) - float(p["stop_loss"] or p["entry"])) * float(p["lot"]) * contract_size
        r_multiple = pnl / risk if risk > 0 else 0.0

        # Execution costs
        commission = _compute_commission(float(p["lot"]), float(p["entry"]), contract_size, params)
        spread_cost = (ask - bid) * float(p["lot"]) * contract_size * 0.5 if (bid and ask) else 0.0
        net_pnl = round(pnl - commission, 2)
        now = int(time.time())

        execution_detail = json_text({
            "commission": commission,
            "slippage_pips": slip_pips,
            "spread_cost": spread_cost,
            "exit_price_raw": raw_exit,
            "exit_price_adj": exit_price,
            "pnl_gross": round(pnl, 2),
            "pnl_net": net_pnl,
        })

        conn.execute(
            "UPDATE bot_positions SET status='closed',closed_at=?,exit_price=?,pnl=?,r_multiple=?,exit_reason=?,updated_at=?,commission=?,slippage=?,spread_cost=?,net_pnl=?,execution_detail=? WHERE id=?",
            (now, exit_price, pnl, r_multiple, note, now, commission, slip_pts, spread_cost, net_pnl, execution_detail, p["id"]),
        )
        wallet = conn.execute("SELECT * FROM wallets WHERE bot_id=?", (bot_id,)).fetchone()
        new_balance = float(wallet["balance"]) + net_pnl
        peak = max(float(wallet["peak_equity"]), new_balance)
        drawdown = ((peak - new_balance) / peak) if peak > 0 else 0.0
        max_dd = max(float(wallet["max_drawdown"]), drawdown)
        conn.execute(
            "UPDATE wallets SET balance=?,realized_pnl=realized_pnl+?,peak_equity=?,max_drawdown=?,total_commission=total_commission+?,total_spread_cost=total_spread_cost+?,total_slippage=total_slippage+?,updated_at=? WHERE bot_id=?",
            (new_balance, net_pnl, peak, max_dd, commission, spread_cost, abs(slip_pts * float(p["lot"]) * contract_size), now, bot_id),
        )
        pos = dict(conn.execute("SELECT *, exit_price AS \"exit\" FROM bot_positions WHERE id=?", (p["id"],)).fetchone())
        alert_engine.notify_trade_close(
            bot_name, side, pnl, note, sym, r_multiple=r_multiple,
            commission=commission, slippage=slip_pts, spread_cost=spread_cost,
            net_pnl=net_pnl, source="manual", bot_id=bot_id,
        )
        return pos


def bot_stats_summary(bot_id: int) -> dict[str, Any]:
    """Per-bot stats summary (mirrors StatsEngine.summary but for any bot)."""
    import math
    closed = storage.query_all(
        "SELECT * FROM bot_positions WHERE bot_id=? AND status='closed' ORDER BY closed_at ASC, id ASC",
        (bot_id,),
    )
    pnls = [float(t.get("pnl") or 0.0) for t in closed]
    net_pnls = [float(t.get("net_pnl") or t.get("pnl") or 0.0) for t in closed]
    rs = [float(t.get("r_multiple") or 0.0) for t in closed if t.get("r_multiple") is not None]
    wins = [p for p in net_pnls if p > 0]
    losses = [p for p in net_pnls if p < 0]
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for pnl in net_pnls:
        equity += pnl
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    wallet = storage.query_one("SELECT * FROM wallets WHERE bot_id=?", (bot_id,)) or {}
    total_commission = sum(float(t.get("commission") or 0.0) for t in closed)
    total_spread_cost = sum(float(t.get("spread_cost") or 0.0) for t in closed)
    total_slippage = sum(abs(float(t.get("slippage") or 0.0)) for t in closed)
    return {
        "closed_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (len(wins) / len(closed)) if closed else 0.0,
        "gross_pnl": round(sum(pnls), 2),
        "net_pnl": round(sum(net_pnls), 2),
        "total_commission": round(total_commission, 2),
        "total_spread_cost": round(total_spread_cost, 2),
        "total_slippage": round(total_slippage, 2),
        "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else None,
        "average_r": (sum(rs) / len(rs)) if rs else 0.0,
        "max_drawdown_usd": round(max_drawdown, 2),
        "balance": float(wallet.get("balance") or 0.0),
        "realized_pnl": float(wallet.get("realized_pnl") or 0.0),
    }


def bot_equity_curve(bot_id: int) -> list[tuple[int, float]]:
    closed = storage.query_all(
        "SELECT closed_at, pnl FROM bot_positions WHERE bot_id=? AND status='closed' AND closed_at IS NOT NULL ORDER BY closed_at ASC, id ASC",
        (bot_id,),
    )
    result: list[tuple[int, float]] = []
    cum = 0.0
    for row in closed:
        cum += float(row["pnl"] or 0.0)
        result.append((int(row["closed_at"]), round(cum, 2)))
    return result


def bot_pnl_by_day(bot_id: int) -> list[tuple[int, float]]:
    from datetime import datetime, timezone
    closed = storage.query_all(
        "SELECT closed_at, pnl FROM bot_positions WHERE bot_id=? AND status='closed' AND closed_at IS NOT NULL ORDER BY closed_at ASC",
        (bot_id,),
    )
    daily: dict[str, float] = {}
    for row in closed:
        dt = datetime.fromtimestamp(int(row["closed_at"]), tz=timezone.utc)
        day_key = dt.strftime("%Y-%m-%d")
        daily[day_key] = daily.get(day_key, 0.0) + float(row["pnl"] or 0.0)
    result: list[tuple[int, float]] = []
    for day_key in sorted(daily):
        ts = int(datetime.strptime(day_key, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
        result.append((ts, round(daily[day_key], 2)))
    return result


def all_pending_orders() -> list[dict[str, Any]]:
    """Get all pending orders across all bots."""
    return storage.query_all(
        "SELECT po.*, b.name AS bot_name FROM bot_pending_orders po JOIN bots b ON b.id=po.bot_id WHERE po.status='pending' ORDER BY po.id DESC"
    )


def all_pending_rejections(limit: int = 50) -> list[dict[str, Any]]:
    """Get pending order rejections across all bots."""
    return storage.query_all(
        "SELECT sl.*, b.name AS bot_name FROM bot_signal_logs sl JOIN bots b ON b.id=sl.bot_id WHERE sl.event_type='pending_rejected' ORDER BY sl.id DESC LIMIT ?",
        (max(1, min(limit, 1000)),),
    )


def delete_bot(bot_id: int) -> bool:
    with storage.transaction() as conn:
        conn.execute("DELETE FROM bot_pending_orders WHERE bot_id=?", (bot_id,))
        conn.execute("DELETE FROM bot_positions WHERE bot_id=?", (bot_id,))
        conn.execute("DELETE FROM bot_signal_logs WHERE bot_id=?", (bot_id,))
        conn.execute("DELETE FROM bot_runtime_state WHERE bot_id=?", (bot_id,))
        conn.execute("DELETE FROM wallets WHERE bot_id=?", (bot_id,))
        conn.execute("DELETE FROM bots WHERE id=?", (bot_id,))
    return True


def ensure_default_bot() -> dict[str, Any] | None:
    """Ensure at least one bot exists. If none, create 'Paper Trading' bot."""
    bots = list_bots()
    if bots:
        return bots[0]
    profile = storage.query_one("SELECT id FROM profiles WHERE name='default'")
    if profile is None:
        from app.multibot.db import migrate
        migrate()
        profile = storage.query_one("SELECT id FROM profiles WHERE name='default'")
        if profile is None:
            return None
    return create_bot(
        profile_id=profile["id"],
        name="Paper Trading",
        initial_balance=settings.initial_balance,
    )
