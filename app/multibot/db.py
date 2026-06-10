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
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def add_column(conn: sqlite3.Connection, table: str, declaration: str) -> None:
    name = declaration.split()[0]
    if name not in columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {declaration}")


def json_text(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def default_parameters() -> dict[str, Any]:
    return {
        "risk_percent": 0.01,
        "ob_strong_score": 6,
        "expiry_candles": 8,
        "tp_r_multiple": 2.0,
        "sl_buffer_ratio": 0.30,
        "max_spread": 1.5,
        "stale_tick_seconds": 10,
        "contract_size": 100.0,
        "lot_step": 0.01,
        "min_lot": 0.01,
        "max_lot": 10.0,
        "allow_tested_once": True,
        "require_m5_confirmation": False,
        "daily_loss_limit_percent": 0.03,
        "max_consecutive_losses": 3,
    }


def migrate() -> dict[str, Any]:
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
                ob_key TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL DEFAULT 'M15',
                side TEXT NOT NULL,
                entry REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                risk_reward REAL NOT NULL,
                risk_percent REAL NOT NULL,
                lot REAL NOT NULL,
                status TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER,
                cancel_reason TEXT,
                filled_at INTEGER,
                updated_at INTEGER,
                UNIQUE(bot_id, ob_key, status)
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
                updated_at INTEGER,
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

            CREATE TABLE IF NOT EXISTS bot_runtime_state (
                bot_id INTEGER PRIMARY KEY,
                latest_tick_json TEXT,
                latest_trend TEXT,
                latest_ob_key TEXT,
                consecutive_losses INTEGER NOT NULL DEFAULT 0,
                daily_realized_pnl REAL NOT NULL DEFAULT 0,
                trading_day TEXT,
                paused_reason TEXT,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS multibot_runtime_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_bot_pending_orders_bot_status ON bot_pending_orders(bot_id, status);
            CREATE INDEX IF NOT EXISTS idx_bot_positions_bot_status ON bot_positions(bot_id, status);
            CREATE INDEX IF NOT EXISTS idx_bot_signal_logs_bot_created ON bot_signal_logs(bot_id, created_at DESC);
            """
        )

        # Upgrade v1.1 tables in-place when needed.
        if table_exists(conn, "bot_pending_orders"):
            for decl in [
                "timeframe TEXT NOT NULL DEFAULT 'M15'",
                "updated_at INTEGER",
            ]:
                add_column(conn, "bot_pending_orders", decl)
        if table_exists(conn, "bot_positions"):
            add_column(conn, "bot_positions", "updated_at INTEGER")

        conn.execute(
            "INSERT OR IGNORE INTO profiles(name, description, enabled, created_at, updated_at) VALUES(?, ?, 1, ?, ?)",
            ("default", "Migrated default profile", now, now),
        )
        profile_id = conn.execute("SELECT id FROM profiles WHERE name='default'").fetchone()["id"]
        conn.execute(
            """
            INSERT OR IGNORE INTO bots(profile_id, name, strategy_type, strategy_version, symbol, timeframe, enabled, parameters_json, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (profile_id, "trend-ob-baseline", "trend_ob", "v1", os.getenv("SYMBOL", "XAUUSD"), "M15", json_text(default_parameters()), now, now),
        )
        bot_id = conn.execute("SELECT id FROM bots WHERE name='trend-ob-baseline'").fetchone()["id"]

        balance = float(os.getenv("INITIAL_BALANCE", "500"))
        realized = 0.0
        if table_exists(conn, "paper_account"):
            row = conn.execute("SELECT balance, realized_pnl FROM paper_account WHERE id=1").fetchone()
            if row:
                balance = float(row["balance"])
                realized = float(row["realized_pnl"] or 0.0)

        conn.execute(
            """
            INSERT OR IGNORE INTO wallets(bot_id, initial_balance, balance, realized_pnl, peak_equity, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (bot_id, balance - realized, balance, realized, balance, now, now),
        )
        wallet_id = conn.execute("SELECT id FROM wallets WHERE bot_id=?", (bot_id,)).fetchone()["id"]

        migrated_trades = 0
        if table_exists(conn, "trades"):
            add_column(conn, "trades", "bot_id INTEGER")
            add_column(conn, "trades", "wallet_id INTEGER")
            conn.execute("UPDATE trades SET bot_id=COALESCE(bot_id, ?), wallet_id=COALESCE(wallet_id, ?)", (bot_id, wallet_id))
            migrated_trades = conn.execute("SELECT COUNT(*) AS n FROM trades WHERE bot_id=?", (bot_id,)).fetchone()["n"]

        migrated_pending = 0
        if table_exists(conn, "pending_orders"):
            cols = columns(conn, "pending_orders")
            required = {"id", "symbol", "side", "entry", "stop_loss", "take_profit", "status", "created_at"}
            if required.issubset(cols):
                for row in conn.execute("SELECT * FROM pending_orders").fetchall():
                    data = dict(row)
                    ob_key = data.get("ob_key") or f"legacy:{data['id']}"
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO bot_pending_orders(
                            bot_id, wallet_id, legacy_pending_id, ob_key, symbol, timeframe, side, entry, stop_loss,
                            take_profit, risk_reward, risk_percent, lot, status, created_at, expires_at, cancel_reason, filled_at, updated_at
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            bot_id, wallet_id, data["id"], ob_key, data["symbol"], data.get("timeframe", "M15"), data["side"],
                            data["entry"], data["stop_loss"], data["take_profit"], float(data.get("risk_reward") or 2.0),
                            float(data.get("risk_percent") or 0.01), float(data.get("lot") or 0.01), data["status"], data["created_at"],
                            data.get("expires_at"), data.get("cancel_reason"), data.get("filled_at"), now,
                        ),
                    )
                migrated_pending = conn.execute("SELECT COUNT(*) AS n FROM bot_pending_orders WHERE bot_id=?", (bot_id,)).fetchone()["n"]

        conn.execute("INSERT OR IGNORE INTO bot_runtime_state(bot_id, updated_at) VALUES(?, ?)", (bot_id, now))
        conn.execute("INSERT OR REPLACE INTO multibot_runtime_settings(key, value, updated_at) VALUES('schema_version', '1.2', ?)", (now,))
        conn.commit()
        return status(conn, migrated_trades, migrated_pending)
    finally:
        conn.close()


def status(conn: sqlite3.Connection | None = None, migrated_trades: int | None = None, migrated_pending: int | None = None) -> dict[str, Any]:
    own = conn is None
    conn = conn or connect()
    try:
        version = conn.execute("SELECT value FROM multibot_runtime_settings WHERE key='schema_version'").fetchone()
        result = {
            "schema_version": version["value"] if version else "unknown",
            "profiles": conn.execute("SELECT COUNT(*) n FROM profiles").fetchone()["n"],
            "bots": conn.execute("SELECT COUNT(*) n FROM bots").fetchone()["n"],
            "wallets": conn.execute("SELECT COUNT(*) n FROM wallets").fetchone()["n"],
            "pending_orders": conn.execute("SELECT COUNT(*) n FROM bot_pending_orders").fetchone()["n"],
            "positions": conn.execute("SELECT COUNT(*) n FROM bot_positions").fetchone()["n"],
        }
        if migrated_trades is not None:
            result["legacy_trades_migrated"] = migrated_trades
        if migrated_pending is not None:
            result["legacy_pending_orders_migrated"] = migrated_pending
        return result
    finally:
        if own:
            conn.close()
