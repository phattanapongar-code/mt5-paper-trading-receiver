from __future__ import annotations

import sqlite3
import threading
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
            """
        )
        # Safe migration from v0.2 databases created before source_ts existed.
        if "source_ts" not in _column_names(conn, "ticks"):
            conn.execute("ALTER TABLE ticks ADD COLUMN source_ts INTEGER")
        cur = conn.execute("SELECT id FROM paper_account WHERE id = 1")
        if cur.fetchone() is None:
            import time
            conn.execute(
                "INSERT INTO paper_account(id, balance, realized_pnl, updated_at) VALUES (1, ?, 0, ?)",
                (settings.initial_balance, int(time.time())),
            )
        conn.commit()


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
