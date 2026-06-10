from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH = os.getenv("DB_PATH", "data/receiver.sqlite3")


def connect() -> sqlite3.Connection:
    path = Path(DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def _add_column(conn: sqlite3.Connection, table: str, declaration: str) -> None:
    name = declaration.split()[0]
    if name not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {declaration}")


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def default_parameters() -> dict[str, Any]:
    return {
        "risk_percent": 0.01,
        "ob_strong_score": 6,
        "expiry_candles": 8,
        "tp_r_multiple": 2.0,
        "sl_buffer_ratio": 0.30,
        "max_spread": 1.5,
        "require_m5_confirmation": False,
        "allow_tested_once": True,
    }


def migrate() -> dict[str, Any]:
    """Idempotently install the multi-bot schema and migrate legacy account data."""
    now = int(time.time())
    conn = connect()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                name TEXT NOT NULL UNIQUE,
                strategy_type TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                parameters_json TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY(profile_id) REFERENCES profiles(id)
            );

            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL UNIQUE,
                initial_balance REAL NOT NULL,
                balance REAL NOT NULL,
                realized_pnl REAL NOT NULL DEFAULT 0,
                currency TEXT NOT NULL DEFAULT 'USD',
                max_drawdown REAL NOT NULL DEFAULT 0,
                peak_equity REAL NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY(bot_id) REFERENCES bots(id)
            );

            CREATE TABLE IF NOT EXISTS bot_pending_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                wallet_id INTEGER NOT NULL,
                legacy_pending_id INTEGER,
                ob_key TEXT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                entry REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                risk_reward REAL,
                risk_percent REAL,
                lot REAL,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER,
                cancel_reason TEXT,
                filled_at INTEGER,
                UNIQUE(bot_id, legacy_pending_id)
            );

            CREATE TABLE IF NOT EXISTS bot_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                wallet_id INTEGER NOT NULL,
                legacy_trade_id INTEGER,
                pending_id INTEGER,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                lot REAL NOT NULL,
                entry REAL NOT NULL,
                stop_loss REAL,
                take_profit REAL,
                status TEXT NOT NULL,
                opened_at INTEGER NOT NULL,
                closed_at INTEGER,
                exit_price REAL,
                pnl REAL,
                r_multiple REAL,
                exit_reason TEXT,
                UNIQUE(bot_id, legacy_trade_id)
            );

            CREATE TABLE IF NOT EXISTS bot_signal_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                payload_json TEXT,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS multibot_runtime_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );
            """
        )

        conn.execute(
            "INSERT OR IGNORE INTO profiles(name, description, enabled, created_at, updated_at) VALUES(?, ?, 1, ?, ?)",
            ("default", "Migrated default profile", now, now),
        )
        profile = conn.execute("SELECT id FROM profiles WHERE name='default'").fetchone()
        assert profile is not None

        conn.execute(
            """
            INSERT OR IGNORE INTO bots(profile_id, name, strategy_type, strategy_version, symbol, timeframe, enabled, parameters_json, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                profile["id"],
                "trend-ob-baseline",
                "trend_ob",
                "v1",
                os.getenv("SYMBOL", "XAUUSD"),
                "M15",
                _json(default_parameters()),
                now,
                now,
            ),
        )
        bot = conn.execute("SELECT id FROM bots WHERE name='trend-ob-baseline'").fetchone()
        assert bot is not None

        balance = float(os.getenv("INITIAL_BALANCE", "500"))
        realized = 0.0
        if _table_exists(conn, "paper_account"):
            account = conn.execute(
                "SELECT balance, realized_pnl FROM paper_account WHERE id=1"
            ).fetchone()
            if account:
                balance = float(account["balance"])
                realized = float(account["realized_pnl"] or 0.0)

        conn.execute(
            """
            INSERT OR IGNORE INTO wallets(bot_id, initial_balance, balance, realized_pnl, peak_equity, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (bot["id"], balance - realized, balance, realized, balance, now, now),
        )
        wallet = conn.execute("SELECT id FROM wallets WHERE bot_id=?", (bot["id"],)).fetchone()
        assert wallet is not None

        migrated_trades = 0
        if _table_exists(conn, "trades"):
            _add_column(conn, "trades", "bot_id INTEGER")
            _add_column(conn, "trades", "wallet_id INTEGER")
            conn.execute(
                "UPDATE trades SET bot_id=COALESCE(bot_id, ?), wallet_id=COALESCE(wallet_id, ?)",
                (bot["id"], wallet["id"]),
            )
            migrated_trades = conn.execute(
                "SELECT COUNT(*) AS n FROM trades WHERE bot_id=?", (bot["id"],)
            ).fetchone()["n"]

        migrated_pending = 0
        if _table_exists(conn, "pending_orders"):
            cols = _columns(conn, "pending_orders")
            required = {"id", "symbol", "side", "entry", "stop_loss", "take_profit", "status", "created_at"}
            if required.issubset(cols):
                rows = conn.execute("SELECT * FROM pending_orders").fetchall()
                for row in rows:
                    data = dict(row)
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO bot_pending_orders(
                            bot_id, wallet_id, legacy_pending_id, ob_key, symbol, side, entry, stop_loss,
                            take_profit, risk_reward, risk_percent, lot, status, created_at, expires_at,
                            cancel_reason, filled_at
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            bot["id"], wallet["id"], data["id"], data.get("ob_key"), data["symbol"],
                            data["side"], data["entry"], data["stop_loss"], data["take_profit"],
                            data.get("risk_reward"), data.get("risk_percent"), data.get("lot"),
                            data["status"], data["created_at"], data.get("expires_at"),
                            data.get("cancel_reason"), data.get("filled_at"),
                        ),
                    )
                migrated_pending = conn.execute(
                    "SELECT COUNT(*) AS n FROM bot_pending_orders WHERE bot_id=?", (bot["id"],)
                ).fetchone()["n"]

        conn.execute(
            "INSERT OR REPLACE INTO multibot_runtime_settings(key, value, updated_at) VALUES('schema_version', '1.1', ?)",
            (now,),
        )
        conn.commit()
        return status(conn, migrated_trades=migrated_trades, migrated_pending=migrated_pending)
    finally:
        conn.close()


def status(conn: sqlite3.Connection | None = None, migrated_trades: int | None = None, migrated_pending: int | None = None) -> dict[str, Any]:
    own = conn is None
    conn = conn or connect()
    try:
        version = conn.execute(
            "SELECT value FROM multibot_runtime_settings WHERE key='schema_version'"
        ).fetchone()
        return {
            "schema_version": version["value"] if version else None,
            "profiles": conn.execute("SELECT COUNT(*) AS n FROM profiles").fetchone()["n"],
            "bots": conn.execute("SELECT COUNT(*) AS n FROM bots").fetchone()["n"],
            "wallets": conn.execute("SELECT COUNT(*) AS n FROM wallets").fetchone()["n"],
            "legacy_trades_migrated": migrated_trades if migrated_trades is not None else 0,
            "legacy_pending_orders_migrated": migrated_pending if migrated_pending is not None else 0,
        }
    finally:
        if own:
            conn.close()
