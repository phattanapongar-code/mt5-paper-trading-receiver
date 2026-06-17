from __future__ import annotations

from pathlib import Path

import pytest

from app.multibot.runtime import (
    _check_gap,
    _trail_stop,
    _round_lot,
    _pip_value,
    _maybe_latency,
)


def test_pip_value_xau():
    assert _pip_value("XAUUSD") == 0.1
    assert _pip_value("XAGUSD") == 0.1
    assert _pip_value("xauusd") == 0.1


def test_pip_value_jpy():
    assert _pip_value("USDJPY") == 0.01
    assert _pip_value("EURJPY") == 0.01


def test_pip_value_forex():
    assert _pip_value("EURUSD") == 0.0001
    assert _pip_value("GBPUSD") == 0.0001


def test_round_lot_standard():
    assert _round_lot(0.123, 0.01, 0.01, 10.0) == 0.12
    assert _round_lot(1.999, 0.01, 0.01, 10.0) == 1.99


def test_round_lot_min_max():
    assert _round_lot(0.001, 0.01, 0.01, 10.0) == 0.01
    assert _round_lot(100.0, 0.01, 0.01, 10.0) == 10.0


def test_round_lot_zero_step():
    assert _round_lot(0.123, 0.0, 0.01, 10.0) == 0.12


def test_check_gap_disabled():
    params = {"gap_check_enabled": False}
    result = _check_gap("XAUUSD", 1000, params)
    assert result is None


def test_check_gap_first_tick():
    params = {"gap_check_enabled": True, "gap_threshold_seconds": 3600, "gap_max_percent": 0.5}
    result = _check_gap("XAUUSD", 1000, params)
    assert result is None


def test_check_gap_within_threshold(tmp_path):
    params = {"gap_check_enabled": True, "gap_threshold_seconds": 3600, "gap_max_percent": 0.5}
    _check_gap("XAUUSD_GAP", 1000, params)
    result = _check_gap("XAUUSD_GAP", 1500, params)
    assert result is None


def test_check_gap_exceeds_threshold(tmp_path):
    params = {"gap_check_enabled": True, "gap_threshold_seconds": 10, "gap_max_percent": 0.5}
    _check_gap("XAUUSD_GAP2", 1000, params)
    result = _check_gap("XAUUSD_GAP2", 100000, params)
    assert result is not None
    assert -0.005 <= result <= 0.005


def test_maybe_latency_noop():
    t0 = _now_ms()
    _maybe_latency({"latency_ms_min": 0, "latency_ms_max": 0})
    dt = _now_ms() - t0
    assert dt < 50


def test_maybe_latency_simulated():
    t0 = _now_ms()
    _maybe_latency({"latency_ms_min": 10, "latency_ms_max": 20})
    dt = _now_ms() - t0
    assert dt >= 5, f"latency too short {dt}ms"


def _now_ms() -> float:
    import time
    return time.time() * 1000


def test_trail_stop_buy_not_enabled(tmp_path):
    _reset_db_runtime(tmp_path)
    from app import storage
    with storage.transaction() as conn:
        _setup_minimal_bot(conn)
        pos = dict(conn.execute("SELECT * FROM bot_positions ORDER BY id DESC LIMIT 1").fetchone())
        params = {"trailing_enabled": False}
        # bid=2305 is below 1R (2310) so breakeven doesn't trigger; trailing disabled → no change
        _trail_stop(conn, pos, 2305.0, 2305.5, params, 100)
        updated = dict(conn.execute("SELECT * FROM bot_positions WHERE id=?", (pos["id"],)).fetchone())
        assert updated["stop_loss"] == pos["stop_loss"]


def test_trail_stop_buy_activates(tmp_path):
    _reset_db_runtime(tmp_path)
    from app import storage
    with storage.transaction() as conn:
        _setup_minimal_bot(conn)
        pos = dict(conn.execute("SELECT * FROM bot_positions ORDER BY id DESC LIMIT 1").fetchone())
        params = {"trailing_enabled": True, "trail_activation_pips": 5, "trail_distance_pips": 3, "trail_step_pips": 1}
        # bid at 2310, entry at 2300, diff = 10 pips > 5 activation
        _trail_stop(conn, pos, 2310.0, 2310.5, params, 100)
        updated = dict(conn.execute("SELECT * FROM bot_positions WHERE id=?", (pos["id"],)).fetchone())
        # new_sl = 2310 - 3*0.1 = 2309.7
        assert updated["stop_loss"] == 2309.7, f"expected 2309.7 got {updated['stop_loss']}"


def test_trail_stop_buy_not_activated(tmp_path):
    _reset_db_runtime(tmp_path)
    from app import storage
    with storage.transaction() as conn:
        _setup_minimal_bot(conn)
        pos = dict(conn.execute("SELECT * FROM bot_positions ORDER BY id DESC LIMIT 1").fetchone())
        params = {"trailing_enabled": True, "trail_activation_pips": 5, "trail_distance_pips": 3, "trail_step_pips": 1}
        # bid at 2300.4, entry at 2300, diff=0.4 < activation=5*0.1=0.5 -> no trail
        _trail_stop(conn, pos, 2300.4, 2300.9, params, 100)
        updated = dict(conn.execute("SELECT * FROM bot_positions WHERE id=?", (pos["id"],)).fetchone())
        assert updated["stop_loss"] == pos["stop_loss"]


def test_trail_stop_sell_activates(tmp_path):
    _reset_db_runtime(tmp_path)
    from app import storage
    with storage.transaction() as conn:
        _setup_minimal_bot(conn, side="sell", entry=2310.0, sl=2320.0)
        pos = dict(conn.execute("SELECT * FROM bot_positions ORDER BY id DESC LIMIT 1").fetchone())
        params = {"trailing_enabled": True, "trail_activation_pips": 5, "trail_distance_pips": 3, "trail_step_pips": 1}
        # ask at 2298, entry at 2310, diff = 12 pips > 5 activation
        _trail_stop(conn, pos, 2297.5, 2298.0, params, 100)
        updated = dict(conn.execute("SELECT * FROM bot_positions WHERE id=?", (pos["id"],)).fetchone())
        # new_sl = 2298 + 3*0.1 = 2298.3
        assert updated["stop_loss"] == 2298.3, f"expected 2298.3 got {updated['stop_loss']}"


# ── Helpers ──

def _reset_db_runtime(tmp_path: Path) -> None:
    from app import storage
    from app.config import settings
    if storage._conn is not None:
        storage._conn.close()
    storage._conn = None
    object.__setattr__(settings, "db_path", str(tmp_path / "runtime.sqlite3"))
    storage.init_db()
    from app.multibot.db import migrate
    migrate()


def _setup_minimal_bot(conn, side: str = "buy", entry: float = 2300.0, sl: float = 2290.0) -> None:
    now = 1700000000
    from app.multibot.db import default_parameters, json_text
    conn.execute("DELETE FROM bot_positions")
    conn.execute("DELETE FROM bots")
    conn.execute("DELETE FROM wallets")
    pid = conn.execute("SELECT id FROM profiles ORDER BY id LIMIT 1").fetchone()[0]
    conn.execute(
        "INSERT INTO bots(profile_id,name,strategy_type,strategy_version,symbol,timeframe,enabled,parameters_json,created_at,updated_at) VALUES(?,?,?,?,?,?,1,?,?,?)",
        (pid, "test_bot", "visual", "v1", "XAUUSD", "M15", json_text(default_parameters()), now, now),
    )
    bid = conn.execute("SELECT id FROM bots ORDER BY id DESC LIMIT 1").fetchone()[0]
    conn.execute(
        "INSERT INTO wallets(bot_id,initial_balance,balance,realized_pnl,peak_equity,created_at,updated_at) VALUES(?,10000,10000,0,10000,?,?)",
        (bid, now, now),
    )
    wid = conn.execute("SELECT id FROM wallets ORDER BY id DESC LIMIT 1").fetchone()[0]
    tp = entry + 2 * (entry - sl) if side == "buy" else entry - 2 * (sl - entry)
    conn.execute(
        "INSERT INTO bot_positions(bot_id,wallet_id,symbol,side,lot,entry,stop_loss,take_profit,status,opened_at,updated_at) VALUES(?,?,?,?,?,?,?,?,'open',?,?)",
        (bid, wid, "XAUUSD", side, 1.0, entry, sl, tp, now, now),
    )
