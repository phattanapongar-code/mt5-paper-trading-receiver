from __future__ import annotations

from pathlib import Path

from app import storage
from app.market_structure import MarketStructureEngine


def _reset_db(tmp_path: Path) -> None:
    if storage._conn is not None:
        storage._conn.close()
    storage._conn = None
    # settings is frozen, but test-only mutation keeps the production API simple.
    object.__setattr__(storage.settings, "db_path", str(tmp_path / "structure.sqlite3"))
    storage.init_db()


def _insert_candles(rows):
    storage.executemany(
        """
        INSERT INTO candles(symbol, timeframe, open_time, close_time, open, high, low, close, tick_count, is_closed, updated_at)
        VALUES (?, 'M15', ?, ?, ?, ?, ?, ?, 10, 1, ?)
        """,
        [
            ("XAUUSD", r[0], r[0] + 900, r[1], r[2], r[3], r[4], r[0] + 900)
            for r in rows
        ],
    )


def test_detects_confirmed_swings_and_close_based_bos(tmp_path):
    _reset_db(tmp_path)
    # window=1 makes the test compact. Pivot high=105 is confirmed after the
    # following candle; later a close crosses above it. Pivot low=98 is also
    # confirmed and later crossed by close.
    rows = [
        (0, 100, 101, 99, 100),
        (900, 100, 105, 100, 104),
        (1800, 104, 104, 101, 102),
        (2700, 102, 106, 101, 106),
        (3600, 106, 107, 98, 99),
        (4500, 99, 103, 99, 101),
        (5400, 101, 102, 97, 97),
    ]
    _insert_candles(rows)
    engine = MarketStructureEngine(swing_window=1, scan_limit=100)
    summary = engine.rebuild("XAUUSD", "M15")
    bos = engine.get_bos("XAUUSD", "M15", 10)

    assert summary["swings"] >= 2
    assert any(event["side"] == "bullish" and event["swing_price"] == 105 for event in bos)
    assert any(event["side"] == "bearish" and event["swing_price"] == 98 for event in bos)


def test_wick_only_break_is_not_bos(tmp_path):
    _reset_db(tmp_path)
    rows = [
        (0, 100, 101, 99, 100),
        (900, 100, 105, 100, 104),
        (1800, 104, 104, 101, 102),
        # Wick is above 105, but close remains below the swing level.
        (2700, 102, 106, 101, 104),
    ]
    _insert_candles(rows)
    engine = MarketStructureEngine(swing_window=1, scan_limit=100)
    engine.rebuild("XAUUSD", "M15")
    bos = engine.get_bos("XAUUSD", "M15", 10)
    assert not any(event["side"] == "bullish" for event in bos)
