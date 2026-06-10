from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from app.multibot.db import connect, default_parameters


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def _decode_bot(bot: dict[str, Any] | None) -> dict[str, Any] | None:
    if bot is None:
        return None
    bot["enabled"] = bool(bot["enabled"])
    bot["parameters"] = json.loads(bot.pop("parameters_json") or "{}")
    return bot


def list_profiles() -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT p.*,
                   COUNT(b.id) AS bot_count,
                   COALESCE(SUM(w.balance), 0) AS total_balance,
                   COALESCE(SUM(w.realized_pnl), 0) AS total_realized_pnl
            FROM profiles p
            LEFT JOIN bots b ON b.profile_id=p.id
            LEFT JOIN wallets w ON w.bot_id=b.id
            GROUP BY p.id
            ORDER BY p.id
            """
        ).fetchall()
        result = [dict(row) for row in rows]
        for item in result:
            item["enabled"] = bool(item["enabled"])
        return result
    finally:
        conn.close()


def create_profile(name: str, description: str = "", enabled: bool = True) -> dict[str, Any]:
    now = int(time.time())
    conn = connect()
    try:
        cur = conn.execute(
            "INSERT INTO profiles(name, description, enabled, created_at, updated_at) VALUES(?, ?, ?, ?, ?)",
            (name, description, 1 if enabled else 0, now, now),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM profiles WHERE id=?", (cur.lastrowid,)).fetchone())
    finally:
        conn.close()


def set_profile_enabled(profile_id: int, enabled: bool) -> dict[str, Any] | None:
    conn = connect()
    try:
        conn.execute(
            "UPDATE profiles SET enabled=?, updated_at=? WHERE id=?",
            (1 if enabled else 0, int(time.time()), profile_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
        result = _row(row)
        if result:
            result["enabled"] = bool(result["enabled"])
        return result
    finally:
        conn.close()


def list_bots(profile_id: int | None = None) -> list[dict[str, Any]]:
    conn = connect()
    try:
        where = " WHERE b.profile_id=?" if profile_id is not None else ""
        params = (profile_id,) if profile_id is not None else ()
        rows = conn.execute(
            f"""
            SELECT b.*, p.name AS profile_name,
                   w.id AS wallet_id, w.initial_balance, w.balance, w.realized_pnl,
                   w.currency, w.max_drawdown, w.peak_equity
            FROM bots b
            JOIN profiles p ON p.id=b.profile_id
            JOIN wallets w ON w.bot_id=b.id
            {where}
            ORDER BY b.id
            """,
            params,
        ).fetchall()
        return [_decode_bot(dict(row)) for row in rows]
    finally:
        conn.close()


def get_bot(bot_id: int) -> dict[str, Any] | None:
    conn = connect()
    try:
        row = conn.execute(
            """
            SELECT b.*, p.name AS profile_name,
                   w.id AS wallet_id, w.initial_balance, w.balance, w.realized_pnl,
                   w.currency, w.max_drawdown, w.peak_equity
            FROM bots b
            JOIN profiles p ON p.id=b.profile_id
            JOIN wallets w ON w.bot_id=b.id
            WHERE b.id=?
            """,
            (bot_id,),
        ).fetchone()
        return _decode_bot(_row(row))
    finally:
        conn.close()


def create_bot(
    profile_id: int,
    name: str,
    strategy_type: str = "trend_ob",
    strategy_version: str = "v1",
    symbol: str = "XAUUSD",
    timeframe: str = "M15",
    enabled: bool = False,
    initial_balance: float = 500.0,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = int(time.time())
    conn = connect()
    try:
        cur = conn.execute(
            """
            INSERT INTO bots(profile_id, name, strategy_type, strategy_version, symbol, timeframe, enabled, parameters_json, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                name,
                strategy_type,
                strategy_version,
                symbol,
                timeframe,
                1 if enabled else 0,
                json.dumps(parameters or default_parameters(), ensure_ascii=False),
                now,
                now,
            ),
        )
        bot_id = cur.lastrowid
        conn.execute(
            """
            INSERT INTO wallets(bot_id, initial_balance, balance, realized_pnl, peak_equity, created_at, updated_at)
            VALUES(?, ?, ?, 0, ?, ?, ?)
            """,
            (bot_id, initial_balance, initial_balance, initial_balance, now, now),
        )
        conn.commit()
    finally:
        conn.close()
    result = get_bot(bot_id)
    assert result is not None
    return result


def clone_bot(bot_id: int, name: str) -> dict[str, Any]:
    source = get_bot(bot_id)
    if source is None:
        raise ValueError("bot not found")
    return create_bot(
        profile_id=source["profile_id"],
        name=name,
        strategy_type=source["strategy_type"],
        strategy_version=source["strategy_version"],
        symbol=source["symbol"],
        timeframe=source["timeframe"],
        enabled=False,
        initial_balance=source["initial_balance"],
        parameters=source["parameters"],
    )


def set_bot_enabled(bot_id: int, enabled: bool) -> dict[str, Any] | None:
    conn = connect()
    try:
        conn.execute(
            "UPDATE bots SET enabled=?, updated_at=? WHERE id=?",
            (1 if enabled else 0, int(time.time()), bot_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_bot(bot_id)


def reset_wallet(bot_id: int, balance: float) -> dict[str, Any] | None:
    now = int(time.time())
    conn = connect()
    try:
        wallet = conn.execute("SELECT id FROM wallets WHERE bot_id=?", (bot_id,)).fetchone()
        if wallet is None:
            return None
        conn.execute("DELETE FROM bot_pending_orders WHERE bot_id=?", (bot_id,))
        conn.execute("DELETE FROM bot_positions WHERE bot_id=?", (bot_id,))
        conn.execute(
            """
            UPDATE wallets
            SET initial_balance=?, balance=?, realized_pnl=0, max_drawdown=0, peak_equity=?, updated_at=?
            WHERE bot_id=?
            """,
            (balance, balance, balance, now, bot_id),
        )
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
                   (SELECT COUNT(*) FROM bot_pending_orders po WHERE po.bot_id=b.id AND po.status='pending') AS pending_orders
            FROM bots b
            JOIN profiles p ON p.id=b.profile_id
            JOIN wallets w ON w.bot_id=b.id
            {where}
            ORDER BY b.id
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
