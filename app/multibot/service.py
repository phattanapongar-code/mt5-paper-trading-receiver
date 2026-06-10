from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from typing import Any

from app.multibot.db import connect, default_parameters, json_text


def _decode(value: str | None) -> dict[str, Any]:
    try:
        return json.loads(value or "{}")
    except Exception:
        return {}


def list_profiles() -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT p.*, COUNT(b.id) AS bot_count,
                   COALESCE(SUM(w.balance),0) AS total_balance,
                   COALESCE(SUM(w.realized_pnl),0) AS total_realized_pnl
            FROM profiles p
            LEFT JOIN bots b ON b.profile_id=p.id
            LEFT JOIN wallets w ON w.bot_id=b.id
            GROUP BY p.id ORDER BY p.id
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def create_profile(name: str, description: str = "", enabled: bool = True) -> dict[str, Any]:
    now = int(time.time())
    conn = connect()
    try:
        cur = conn.execute(
            "INSERT INTO profiles(name, description, enabled, created_at, updated_at) VALUES(?,?,?,?,?)",
            (name, description, 1 if enabled else 0, now, now),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM profiles WHERE id=?", (cur.lastrowid,)).fetchone())
    finally:
        conn.close()


def set_profile_enabled(profile_id: int, enabled: bool) -> dict[str, Any] | None:
    conn = connect()
    try:
        conn.execute("UPDATE profiles SET enabled=?, updated_at=? WHERE id=?", (1 if enabled else 0, int(time.time()), profile_id))
        conn.commit()
        row = conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_bots(profile_id: int | None = None) -> list[dict[str, Any]]:
    conn = connect()
    try:
        where = "WHERE b.profile_id=?" if profile_id is not None else ""
        params = (profile_id,) if profile_id is not None else ()
        rows = conn.execute(
            f"""
            SELECT b.*, p.name AS profile_name, p.enabled AS profile_enabled,
                   w.id AS wallet_id, w.initial_balance, w.balance, w.realized_pnl,
                   w.currency, w.max_drawdown, w.peak_equity,
                   COALESCE((SELECT COUNT(*) FROM bot_pending_orders x WHERE x.bot_id=b.id AND x.status='pending'),0) AS pending_count,
                   COALESCE((SELECT COUNT(*) FROM bot_positions x WHERE x.bot_id=b.id AND x.status='open'),0) AS open_position_count,
                   s.latest_trend, s.paused_reason
            FROM bots b
            JOIN profiles p ON p.id=b.profile_id
            JOIN wallets w ON w.bot_id=b.id
            LEFT JOIN bot_runtime_state s ON s.bot_id=b.id
            {where}
            ORDER BY b.id
            """,
            params,
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["parameters"] = _decode(item.pop("parameters_json", "{}"))
            out.append(item)
        return out
    finally:
        conn.close()


def get_bot(bot_id: int) -> dict[str, Any] | None:
    bots = [b for b in list_bots() if b["id"] == bot_id]
    return bots[0] if bots else None


def create_bot(profile_id: int, name: str, strategy_type: str = "trend_ob", strategy_version: str = "v1",
               symbol: str = "XAUUSD", timeframe: str = "M15", enabled: bool = False,
               initial_balance: float = 500.0, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    now = int(time.time())
    params = default_parameters()
    params.update(parameters or {})
    conn = connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO bots(profile_id,name,strategy_type,strategy_version,symbol,timeframe,enabled,parameters_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (profile_id, name, strategy_type, strategy_version, symbol, timeframe, 1 if enabled else 0, json_text(params), now, now),
        )
        bot_id = cur.lastrowid
        conn.execute(
            "INSERT INTO wallets(bot_id,initial_balance,balance,realized_pnl,peak_equity,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (bot_id, initial_balance, initial_balance, 0.0, initial_balance, now, now),
        )
        conn.execute("INSERT INTO bot_runtime_state(bot_id, updated_at) VALUES(?,?)", (bot_id, now))
        conn.commit()
        return get_bot(bot_id) or {}
    finally:
        conn.close()


def clone_bot(bot_id: int, name: str) -> dict[str, Any]:
    source = get_bot(bot_id)
    if source is None:
        raise ValueError("bot not found")
    return create_bot(source["profile_id"], name, source["strategy_type"], source["strategy_version"], source["symbol"], source["timeframe"], False, source["initial_balance"], source["parameters"])


def set_bot_enabled(bot_id: int, enabled: bool) -> dict[str, Any] | None:
    conn = connect()
    try:
        conn.execute("UPDATE bots SET enabled=?, updated_at=? WHERE id=?", (1 if enabled else 0, int(time.time()), bot_id))
        conn.commit()
    finally:
        conn.close()
    return get_bot(bot_id)


def update_bot_parameters(bot_id: int, parameters: dict[str, Any]) -> dict[str, Any] | None:
    bot = get_bot(bot_id)
    if bot is None:
        return None
    merged = default_parameters()
    merged.update(bot.get("parameters") or {})
    merged.update(parameters)
    conn = connect()
    try:
        conn.execute("UPDATE bots SET parameters_json=?, updated_at=? WHERE id=?", (json_text(merged), int(time.time()), bot_id))
        conn.commit()
    finally:
        conn.close()
    return get_bot(bot_id)


def get_wallet(bot_id: int) -> dict[str, Any] | None:
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM wallets WHERE bot_id=?", (bot_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def reset_wallet(bot_id: int, balance: float) -> dict[str, Any] | None:
    now = int(time.time())
    conn = connect()
    try:
        wallet = conn.execute("SELECT id FROM wallets WHERE bot_id=?", (bot_id,)).fetchone()
        if wallet is None:
            return None
        conn.execute("DELETE FROM bot_pending_orders WHERE bot_id=?", (bot_id,))
        conn.execute("DELETE FROM bot_positions WHERE bot_id=?", (bot_id,))
        conn.execute("UPDATE wallets SET initial_balance=?, balance=?, realized_pnl=0, max_drawdown=0, peak_equity=?, updated_at=? WHERE bot_id=?", (balance, balance, balance, now, bot_id))
        conn.execute("UPDATE bot_runtime_state SET consecutive_losses=0,daily_realized_pnl=0,paused_reason=NULL,updated_at=? WHERE bot_id=?", (now, bot_id))
        conn.commit()
        return dict(conn.execute("SELECT * FROM wallets WHERE bot_id=?", (bot_id,)).fetchone())
    finally:
        conn.close()


def compare(bot_ids: list[int] | None = None) -> list[dict[str, Any]]:
    conn = connect()
    try:
        where = ""
        params: list[Any] = []
        if bot_ids:
            where = f" WHERE b.id IN ({','.join('?' for _ in bot_ids)})"
            params = list(bot_ids)
        rows = conn.execute(
            f"""
            SELECT b.id AS bot_id, b.name, p.name AS profile_name, b.strategy_type, b.strategy_version,
                   w.initial_balance, w.balance, w.realized_pnl, w.max_drawdown,
                   (SELECT COUNT(*) FROM bot_positions bp WHERE bp.bot_id=b.id AND bp.status='closed') AS closed_trades,
                   (SELECT COUNT(*) FROM bot_positions bp WHERE bp.bot_id=b.id AND bp.status='open') AS open_positions,
                   (SELECT COUNT(*) FROM bot_pending_orders po WHERE po.bot_id=b.id AND po.status='pending') AS pending_orders,
                   (SELECT COUNT(*) FROM bot_positions bp WHERE bp.bot_id=b.id AND bp.status='closed' AND bp.pnl>0) AS wins,
                   (SELECT COALESCE(SUM(bp.pnl),0) FROM bot_positions bp WHERE bp.bot_id=b.id AND bp.status='closed') AS net_pnl
            FROM bots b JOIN profiles p ON p.id=b.profile_id JOIN wallets w ON w.bot_id=b.id
            {where} ORDER BY b.id
            """,
            params,
        ).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["win_rate"] = (item["wins"] / item["closed_trades"] * 100.0) if item["closed_trades"] else 0.0
            out.append(item)
        return out
    finally:
        conn.close()


def bot_state(bot_id: int) -> dict[str, Any] | None:
    bot = get_bot(bot_id)
    if not bot:
        return None
    conn = connect()
    try:
        pending = conn.execute("SELECT * FROM bot_pending_orders WHERE bot_id=? AND status='pending' ORDER BY id DESC LIMIT 1", (bot_id,)).fetchone()
        position = conn.execute("SELECT * FROM bot_positions WHERE bot_id=? AND status='open' ORDER BY id DESC LIMIT 1", (bot_id,)).fetchone()
        state = conn.execute("SELECT * FROM bot_runtime_state WHERE bot_id=?", (bot_id,)).fetchone()
        trades = conn.execute("SELECT * FROM bot_positions WHERE bot_id=? ORDER BY id DESC LIMIT 20", (bot_id,)).fetchall()
        result = {"bot": bot, "pending": dict(pending) if pending else None, "position": dict(position) if position else None, "runtime": dict(state) if state else None, "trades": [dict(x) for x in trades]}
        return result
    finally:
        conn.close()


def signal_logs(bot_id: int, limit: int = 100) -> list[dict[str, Any]]:
    conn = connect()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM bot_signal_logs WHERE bot_id=? ORDER BY id DESC LIMIT ?", (bot_id, limit)).fetchall()]
    finally:
        conn.close()


def trades(bot_id: int, limit: int = 100) -> list[dict[str, Any]]:
    conn = connect()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM bot_positions WHERE bot_id=? ORDER BY id DESC LIMIT ?", (bot_id, limit)).fetchall()]
    finally:
        conn.close()
