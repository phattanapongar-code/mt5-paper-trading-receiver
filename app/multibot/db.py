from __future__ import annotations

import json
import time
from typing import Any

from app import storage
from app.config import settings


def json_text(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def default_parameters() -> dict[str, Any]:
    return {
        "risk_percent": settings.trend_risk_percent,
        "ob_strong_score": settings.ob_strong_score,
        "expiry_candles": settings.pending_expiry_candles,
        "tp_r_multiple": settings.pending_tp_r_multiple,
        "sl_buffer_ratio": settings.pending_sl_buffer_ratio,
        "max_spread": settings.max_spread,
        "stale_tick_seconds": settings.stale_tick_seconds,
        "contract_size": settings.contract_size,
        "lot_step": settings.lot_step,
        "min_lot": settings.min_lot,
        "max_lot": settings.max_lot,
        "allow_tested_once": True,
        "require_m5_confirmation": False,
        "ob_max_age_candles": 20,
        "min_rr": 1.5,
        "sl_atr_multiple": 1.5,
        "tp_atr_multiple": 3.0,
        "rsi_oversold": 30.0,
        "rsi_overbought": 70.0,
        "rsi_trend_filter": True,
        "daily_loss_limit_percent": 0.03,
        "max_consecutive_losses": 3,
        "trailing_enabled": False,
        "trail_activation_pips": 10,
        "trail_distance_pips": 5,
        "trail_step_pips": 1,
        "commission_per_lot": settings.commission_per_lot,
        "commission_type": settings.commission_type,
        "commission_pct": settings.commission_pct,
        "slippage_sigma": settings.slippage_sigma,
        "slippage_max_pips": settings.slippage_max_pips,
        "latency_ms_min": settings.latency_ms_min,
        "latency_ms_max": settings.latency_ms_max,
        "gap_check_enabled": settings.gap_check_enabled,
        "gap_max_percent": settings.gap_max_percent,
        "gap_threshold_seconds": settings.gap_threshold_seconds,
    }


def migrate() -> dict[str, Any]:
    now = int(time.time())
    with storage.transaction() as conn:
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
                strategy_type TEXT NOT NULL DEFAULT 'visual',
                strategy_version TEXT NOT NULL DEFAULT 'v1',
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 0,
                parameters_json TEXT NOT NULL DEFAULT '{}',
                visual_strategy_id INTEGER,
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
        existing_bpo = {row["name"] for row in conn.execute("PRAGMA table_info(bot_pending_orders)").fetchall()}
        if "timeframe" not in existing_bpo:
            conn.execute("ALTER TABLE bot_pending_orders ADD COLUMN timeframe TEXT NOT NULL DEFAULT 'M15'")
        if                 "updated_at" not in existing_bpo:
            conn.execute("ALTER TABLE bot_pending_orders ADD COLUMN updated_at INTEGER")

        existing_bp = {row["name"] for row in conn.execute("PRAGMA table_info(bot_positions)").fetchall()}
        if "updated_at" not in existing_bp:
            conn.execute("ALTER TABLE bot_positions ADD COLUMN updated_at INTEGER")

        # Upgrade v2.5 — execution realism columns
        if "commission" not in existing_bp:
            conn.execute("ALTER TABLE bot_positions ADD COLUMN commission REAL DEFAULT 0")
        if "slippage" not in existing_bp:
            conn.execute("ALTER TABLE bot_positions ADD COLUMN slippage REAL DEFAULT 0")
        if "spread_cost" not in existing_bp:
            conn.execute("ALTER TABLE bot_positions ADD COLUMN spread_cost REAL DEFAULT 0")
        if "net_pnl" not in existing_bp:
            conn.execute("ALTER TABLE bot_positions ADD COLUMN net_pnl REAL")
        if "execution_detail" not in existing_bp:
            conn.execute("ALTER TABLE bot_positions ADD COLUMN execution_detail TEXT")

        existing_w = {row["name"] for row in conn.execute("PRAGMA table_info(wallets)").fetchall()}
        if "total_commission" not in existing_w:
            conn.execute("ALTER TABLE wallets ADD COLUMN total_commission REAL DEFAULT 0")
        if "total_spread_cost" not in existing_w:
            conn.execute("ALTER TABLE wallets ADD COLUMN total_spread_cost REAL DEFAULT 0")
        if "total_slippage" not in existing_w:
            conn.execute("ALTER TABLE wallets ADD COLUMN total_slippage REAL DEFAULT 0")

        # Upgrade v2.6 — visual strategy column
        existing_b = {row["name"] for row in conn.execute("PRAGMA table_info(bots)").fetchall()}
        if "visual_strategy_id" not in existing_b:
            conn.execute("ALTER TABLE bots ADD COLUMN visual_strategy_id INTEGER REFERENCES visual_strategies(id)")

        conn.execute(
            "INSERT OR IGNORE INTO profiles(name, description, enabled, created_at, updated_at) VALUES(?, ?, 1, ?, ?)",
            ("default", "Default profile", now, now),
        )
        profile_id = conn.execute("SELECT id FROM profiles WHERE name='default'").fetchone()["id"]

        any_bot = conn.execute("SELECT id FROM bots LIMIT 1").fetchone()
        if any_bot is None:
            old_bot = conn.execute("SELECT id FROM bots WHERE name='trend-ob-baseline'").fetchone()
            if old_bot:
                conn.execute("UPDATE bots SET name='Paper Trading', updated_at=? WHERE id=?", (now, old_bot["id"]))
                bot_id = old_bot["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO bots(profile_id, name, strategy_type, strategy_version, symbol, timeframe, enabled, parameters_json, created_at, updated_at) VALUES(?,?,?,?,?,?,0,?,?,?)",
                    (profile_id, "Paper Trading", "visual", "v1", settings.symbol, "M15", json_text(default_parameters()), now, now),
                )
                bot_id = cur.lastrowid
        else:
            bot_id = any_bot["id"]

        balance = settings.initial_balance
        realized = 0.0
        if storage.table_exists("paper_account"):
            row = storage.query_one("SELECT balance, realized_pnl FROM paper_account WHERE id=1")
            if row:
                balance = float(row["balance"])
                realized = float(row.get("realized_pnl") or 0.0)

        conn.execute(
            """
            INSERT OR IGNORE INTO wallets(bot_id, initial_balance, balance, realized_pnl, peak_equity, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (bot_id, balance - realized, balance, realized, balance, now, now),
        )
        wallet_id = conn.execute("SELECT id FROM wallets WHERE bot_id=?", (bot_id,)).fetchone()["id"]

        # Migrate legacy trades to bot_positions
        if storage.table_exists("trades"):
            for row in conn.execute("SELECT * FROM trades").fetchall():
                t = dict(row)
                bt = t.get("bot_id") or bot_id
                wt = t.get("wallet_id") or wallet_id
                status = str(t["status"])
                r_multiple_val = t.get("r_multiple")
                exit_price = t.get("exit")
                pnl_val = t.get("pnl")
                closed_at_val = t.get("closed_at")
                exit_reason_val = t.get("exit_reason") or (str(t.get("note", "")) if status == "closed" else None)
                conn.execute(
                    """
                    INSERT OR IGNORE INTO bot_positions(
                        bot_id, wallet_id, legacy_trade_id, symbol, side, lot, entry, stop_loss, take_profit,
                        status, opened_at, closed_at, exit_price, pnl, r_multiple, exit_reason, updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (bt, wt, t["id"], t["symbol"], t["side"], t["lot"], t["entry"],
                     t.get("stop_loss"), t.get("take_profit"), status, t["opened_at"],
                     closed_at_val, exit_price, pnl_val, r_multiple_val, exit_reason_val, now),
                )

        # Migrate legacy pending orders to bot_pending_orders
        if storage.table_exists("pending_orders"):
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

        conn.execute("INSERT OR IGNORE INTO bot_runtime_state(bot_id, updated_at) VALUES(?, ?)", (bot_id, now))
        conn.execute("INSERT OR REPLACE INTO multibot_runtime_settings(key, value, updated_at) VALUES('schema_version', '2.5.1', ?)", (now,))
    return get_status()


def get_status() -> dict[str, Any]:
    version = storage.query_one("SELECT value FROM multibot_runtime_settings WHERE key='schema_version'")
    return {
        "schema_version": version["value"] if version else "unknown",
        "profiles": (storage.query_one("SELECT COUNT(*) n FROM profiles") or {}).get("n", 0),
        "bots": (storage.query_one("SELECT COUNT(*) n FROM bots") or {}).get("n", 0),
        "wallets": (storage.query_one("SELECT COUNT(*) n FROM wallets") or {}).get("n", 0),
        "pending_orders": (storage.query_one("SELECT COUNT(*) n FROM bot_pending_orders") or {}).get("n", 0),
        "positions": (storage.query_one("SELECT COUNT(*) n FROM bot_positions") or {}).get("n", 0),
    }
