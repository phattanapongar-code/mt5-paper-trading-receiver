from __future__ import annotations

from pathlib import Path

from app import storage
from app.order_blocks import OrderBlockEngine


def _reset_db(tmp_path: Path) -> None:
    if storage._conn is not None:
        storage._conn.close()
    storage._conn = None
    object.__setattr__(storage.settings, "db_path", str(tmp_path / "ob.sqlite3"))
    storage.init_db()


def _insert_candle(open_time: int, open_: float, high: float, low: float, close: float) -> None:
    storage.execute(
        """
        INSERT INTO candles(symbol, timeframe, open_time, close_time, open, high, low, close, tick_count, is_closed, updated_at)
        VALUES ('XAUUSD', 'M15', ?, ?, ?, ?, ?, ?, 10, 1, ?)
        """,
        (open_time, open_time + 900, open_, high, low, close, open_time + 900),
    )


def _seed_bearish_ob(tmp_path: Path, retests: int = 0) -> OrderBlockEngine:
    _reset_db(tmp_path)
    # Stable history for ATR/body baselines.
    t = 0
    for i in range(24):
        base = 100.0 + (i % 3) * 0.1
        _insert_candle(t, base, base + 1.0, base - 1.0, base + (0.3 if i % 2 == 0 else -0.3))
        t += 900

    ob_time = t
    _insert_candle(ob_time, 100.0, 101.0, 99.5, 100.8)  # bullish origin candle
    t += 900
    _insert_candle(t, 100.7, 100.9, 97.5, 98.0)
    t += 900
    break_time = t
    _insert_candle(break_time, 98.0, 98.2, 94.0, 94.5)

    storage.execute(
        """
        INSERT INTO swing_points(symbol, timeframe, side, pivot_open_time, price, created_at)
        VALUES ('XAUUSD', 'M15', 'high', ?, 101.0, ?)
        """,
        (ob_time, ob_time),
    )
    storage.execute(
        """
        INSERT INTO bos_events(symbol, timeframe, side, swing_open_time, swing_price, break_open_time, break_close, created_at)
        VALUES ('XAUUSD', 'M15', 'bearish', ?, 96.0, ?, 94.5, ?)
        """,
        (ob_time - 900, break_time, break_time),
    )

    for _ in range(retests):
        t += 900
        _insert_candle(t, 99.0, 100.2, 98.8, 99.5)  # overlaps zone but closes below ob_high

    return OrderBlockEngine(swing_tolerance=0.3, scan_limit=1000)


def test_detects_strong_bearish_order_block(tmp_path):
    engine = _seed_bearish_ob(tmp_path)
    summary = engine.rebuild("XAUUSD", "M15")
    rows = engine.get_order_blocks("XAUUSD", "M15")

    assert summary["total"] == 1
    assert summary["strong"] == 1
    assert rows[0]["side"] == "bearish"
    assert rows[0]["status"] == "active"
    assert rows[0]["retest_count"] == 0
    assert rows[0]["score"] >= 6


def test_one_retest_is_preserved_but_second_invalidates(tmp_path):
    engine = _seed_bearish_ob(tmp_path, retests=1)
    engine.rebuild("XAUUSD", "M15")
    first = engine.get_order_blocks("XAUUSD", "M15")[0]
    assert first["status"] == "tested_once"
    assert first["retest_count"] == 1

    # Add a second touch and rebuild: candidate is invalidated.
    latest = storage.query_one("SELECT MAX(open_time) AS t FROM candles WHERE timeframe = 'M15'")["t"]
    _insert_candle(int(latest) + 900, 99.2, 100.4, 99.0, 99.6)
    engine.rebuild("XAUUSD", "M15")
    second = engine.get_order_blocks("XAUUSD", "M15")[0]
    assert second["status"] == "invalidated"
    assert second["retest_count"] == 2
