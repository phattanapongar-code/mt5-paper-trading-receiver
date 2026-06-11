from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from app.config import settings

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            db_path = Path(settings.db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(db_path, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA synchronous=NORMAL")
        return _conn


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def init_db() -> None:
    conn = get_conn()
    with _lock:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                type TEXT NOT NULL,
                bid REAL NOT NULL,
                ask REAL NOT NULL,
                mid REAL NOT NULL,
                spread REAL NOT NULL,
                seq INTEGER,
                ts INTEGER NOT NULL,
                received_at INTEGER NOT NULL,
                source_ts INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_ticks_ts ON ticks(ts DESC);
            CREATE INDEX IF NOT EXISTS idx_ticks_symbol_ts ON ticks(symbol, ts DESC);

            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                open_time INTEGER NOT NULL,
                close_time INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                tick_count INTEGER NOT NULL DEFAULT 0,
                is_closed INTEGER NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL,
                UNIQUE(symbol, timeframe, open_time)
            );

            CREATE INDEX IF NOT EXISTS idx_candles_lookup
                ON candles(symbol, timeframe, open_time DESC);

            CREATE TABLE IF NOT EXISTS history_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                source TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                offset_seconds INTEGER NOT NULL DEFAULT 0,
                imported_m1 INTEGER NOT NULL,
                rebuilt_m5 INTEGER NOT NULL,
                rebuilt_m15 INTEGER NOT NULL,
                rebuilt_h1 INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_replay_runs_created_at ON replay_runs(created_at DESC);

            CREATE TABLE IF NOT EXISTS paper_account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                balance REAL NOT NULL,
                realized_pnl REAL NOT NULL DEFAULT 0,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                lot REAL NOT NULL,
                entry REAL NOT NULL,
                exit REAL,
                stop_loss REAL,
                take_profit REAL,
                status TEXT NOT NULL,
                opened_at INTEGER NOT NULL,
                closed_at INTEGER,
                pnl REAL,
                note TEXT
            );

            CREATE TABLE IF NOT EXISTS signal_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                payload TEXT,
                ts INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_signal_logs_ts ON signal_logs(ts DESC);

            CREATE TABLE IF NOT EXISTS swing_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('high', 'low')),
                pivot_open_time INTEGER NOT NULL,
                price REAL NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(symbol, timeframe, side, pivot_open_time)
            );

            CREATE INDEX IF NOT EXISTS idx_swing_points_lookup
                ON swing_points(symbol, timeframe, pivot_open_time DESC);

            CREATE TABLE IF NOT EXISTS bos_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('bullish', 'bearish')),
                swing_open_time INTEGER NOT NULL,
                swing_price REAL NOT NULL,
                break_open_time INTEGER NOT NULL,
                break_close REAL NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(symbol, timeframe, side, swing_open_time, break_open_time)
            );

            CREATE INDEX IF NOT EXISTS idx_bos_events_lookup
                ON bos_events(symbol, timeframe, break_open_time DESC);


            CREATE TABLE IF NOT EXISTS order_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('bullish', 'bearish')),
                bos_id INTEGER NOT NULL,
                swing_open_time INTEGER NOT NULL,
                swing_price REAL NOT NULL,
                break_open_time INTEGER NOT NULL,
                break_close REAL NOT NULL,
                ob_open_time INTEGER NOT NULL,
                ob_open REAL NOT NULL,
                ob_close REAL NOT NULL,
                ob_low REAL NOT NULL,
                ob_high REAL NOT NULL,
                impulse_body REAL NOT NULL,
                impulse_range REAL NOT NULL,
                impulse_body_ratio REAL,
                impulse_range_ratio REAL,
                origin_swing_open_time INTEGER,
                origin_swing_price REAL,
                swing_distance_ratio REAL,
                retest_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL CHECK(status IN ('active', 'tested_once', 'invalidated', 'expired')),
                score INTEGER NOT NULL,
                is_strong INTEGER NOT NULL DEFAULT 0,
                score_reasons TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                UNIQUE(symbol, timeframe, bos_id)
            );

            CREATE INDEX IF NOT EXISTS idx_order_blocks_lookup
                ON order_blocks(symbol, timeframe, break_open_time DESC);

            CREATE INDEX IF NOT EXISTS idx_order_blocks_active
                ON order_blocks(symbol, timeframe, status, is_strong);

            CREATE TABLE IF NOT EXISTS pending_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),
                ob_id INTEGER NOT NULL,
                ob_side TEXT NOT NULL CHECK(ob_side IN ('bullish', 'bearish')),
                ob_break_open_time INTEGER NOT NULL,
                source_trend TEXT NOT NULL CHECK(source_trend IN ('BULLISH', 'BEARISH')),
                entry REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                risk_distance REAL NOT NULL,
                risk_reward REAL NOT NULL,
                spread_at_creation REAL NOT NULL,
                created_open_time INTEGER NOT NULL,
                expires_open_time INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'cancelled', 'rejected', 'filled')),
                cancel_reason TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pending_orders_status
                ON pending_orders(symbol, status, id DESC);

            CREATE INDEX IF NOT EXISTS idx_pending_orders_ob
                ON pending_orders(ob_id, id DESC);

            CREATE INDEX IF NOT EXISTS idx_pending_orders_ob_stable
                ON pending_orders(symbol, timeframe, ob_side, ob_break_open_time, id DESC);

            CREATE TABLE IF NOT EXISTS replay_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at INTEGER NOT NULL
            );
            """
        )
        # Safe additive migrations: old SQLite data remains valid across patches.
        if "source_ts" not in _column_names(conn, "ticks"):
            conn.execute("ALTER TABLE ticks ADD COLUMN source_ts INTEGER")
        trade_columns = _column_names(conn, "trades")
        for name, sql_type in {
            "pending_order_id": "INTEGER",
            "strategy_id": "TEXT",
            "risk_percent": "REAL",
            "risk_usd": "REAL",
            "initial_risk_distance": "REAL",
            "r_multiple": "REAL",
            "exit_reason": "TEXT",
        }.items():
            if name not in trade_columns:
                conn.execute(f"ALTER TABLE trades ADD COLUMN {name} {sql_type}")
        pending_columns = _column_names(conn, "pending_orders")
        for name, sql_type in {
            "filled_at": "INTEGER",
            "fill_price": "REAL",
            "trade_id": "INTEGER",
        }.items():
            if name not in pending_columns:
                conn.execute(f"ALTER TABLE pending_orders ADD COLUMN {name} {sql_type}")
        if "bot_id" not in _column_names(conn, "signal_logs"):
            conn.execute("ALTER TABLE signal_logs ADD COLUMN bot_id INTEGER")
        cur = conn.execute("SELECT id FROM paper_account WHERE id = 1")
        if cur.fetchone() is None:
            import time
            conn.execute(
                "INSERT INTO paper_account(id, balance, realized_pnl, updated_at) VALUES (1, ?, 0, ?)",
                (settings.initial_balance, int(time.time())),
            )
        conn.commit()


def cleanup_old_data(max_tick_days: int = 7, max_signal_days: int = 30, max_replay_days: int = 7) -> dict[str, int]:
    """Startup TTL cleanup — prune ticks, signal_logs, replay_runs older than N days.

    Runs synchronously at boot so the database never grows unbounded even
    when the receiver is started infrequently.
    """
    now = int(time.time())
    tick_cutoff = now - max_tick_days * 86400
    signal_cutoff = now - max_signal_days * 86400
    replay_cutoff = now - max_replay_days * 86400

    deleted_ticks = execute("DELETE FROM ticks WHERE ts < ?", (tick_cutoff,)).rowcount
    deleted_signals = execute("DELETE FROM signal_logs WHERE ts < ?", (signal_cutoff,)).rowcount
    deleted_replays = execute("DELETE FROM replay_runs WHERE created_at < ?", (replay_cutoff,)).rowcount

    total = deleted_ticks + deleted_signals + deleted_replays
    if total:
        get_conn().execute("PRAGMA wal_checkpoint(TRUNCATE)")

    return {
        "deleted_ticks": deleted_ticks,
        "deleted_signal_logs": deleted_signals,
        "deleted_replay_runs": deleted_replays,
    }


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    conn = get_conn()
    with _lock:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def execute(sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
    conn = get_conn()
    with _lock:
        cur = conn.execute(sql, tuple(params))
        conn.commit()
        return cur


def executemany(sql: str, params: Sequence[Iterable[Any]]) -> None:
    conn = get_conn()
    with _lock:
        conn.executemany(sql, [tuple(p) for p in params])
        conn.commit()


def query_one(sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    conn = get_conn()
    with _lock:
        row = conn.execute(sql, tuple(params)).fetchone()
    return dict(row) if row else None


def query_all(sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    conn = get_conn()
    with _lock:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(r) for r in rows]
