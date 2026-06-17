from __future__ import annotations

from pathlib import Path

import pytest

from app import storage
from app.config import settings
from app.multibot.db import migrate
from app.multibot.runtime import (
    _gaussian_slippage,
    _compute_commission,
    _apply_exit_slippage,
    _apply_entry_slippage,
    _close_position,
    _evaluate_bot,
)
from app.multibot.service import (
    open_position,
    close_position,
    bot_stats_summary,
)


def _reset_db(tmp_path: Path) -> None:
    if storage._conn is not None:
        storage._conn.close()
    storage._conn = None
    object.__setattr__(settings, "db_path", str(tmp_path / "exec.sqlite3"))
    storage.init_db()
    migrate()


def _insert_candle(open_time: int, close: float, high: float = 0, low: float = 0) -> None:
    h = high or close + 0.5
    l = low or close - 0.5
    storage.execute(
        """
        INSERT INTO candles(symbol, timeframe, open_time, close_time, open, high, low, close, tick_count, is_closed, updated_at)
        VALUES ('XAUUSD', 'M15', ?, ?, ?, ?, ?, ?, 10, 1, ?)
        """,
        (open_time, open_time + 900, close - 0.2, h, l, close, open_time + 900),
    )


def _seed_bullish(tmp_path: Path) -> int:
    _reset_db(tmp_path)
    now = 1700000000
    for i in range(400):
        t = now + i * 900
        _insert_candle(t, 2300.0 + i * 0.1, 2300.5 + i * 0.1, 2299.5 + i * 0.1)
    # Insert a bearish OB for M15
    from app.candle_engine import CandleEngine
    ce = CandleEngine()
    for i in range(5):
        t = now - (5 - i) * 60
        ce.update_tick("XAUUSD", 2305.0, 2305.5, t)
    from app.order_blocks import OrderBlockEngine
    obe = OrderBlockEngine()
    obe.rebuild_all("XAUUSD")
    from app.market_structure import MarketStructureEngine
    mse = MarketStructureEngine()
    mse.rebuild_all("XAUUSD")
    return now


def test_gaussian_slippage_bounds(tmp_path):
    """Slippage must never exceed max_pips."""
    for _ in range(100):
        slip = _gaussian_slippage(0.15, 0.5)
        assert -0.5 <= slip <= 0.5, f"slippage {slip} out of bounds"
    # With small sigma, most values should be near 0
    slips = [_gaussian_slippage(0.01, 0.5) for _ in range(50)]
    avg = sum(abs(s) for s in slips) / len(slips)
    assert avg < 0.1, f"avg slippage {avg} too high for small sigma"


def test_commission_fixed(tmp_path):
    """Fixed commission = lot * commission_per_lot."""
    params = {"commission_type": "fixed", "commission_per_lot": 3.5}
    comm = _compute_commission(1.0, 2300.0, 100.0, params)
    assert comm == 3.5
    comm = _compute_commission(0.5, 2300.0, 100.0, params)
    assert comm == 1.75


def test_commission_percentage(tmp_path):
    """Percentage commission = lot * cs * entry * pct."""
    params = {"commission_type": "percentage", "commission_pct": 0.0001}
    comm = _compute_commission(1.0, 2300.0, 100.0, params)
    assert comm == 23.0  # 1 * 100 * 2300 * 0.0001


def test_apply_exit_slippage_buy(tmp_path):
    """Buy exit: slippage makes price lower (worse for seller)."""
    price = _apply_exit_slippage(2300.0, "buy", 0.15)
    assert price == 2299.85  # 2300 - 0.15


def test_apply_exit_slippage_sell(tmp_path):
    """Sell exit: slippage makes price higher (worse for buyer)."""
    price = _apply_exit_slippage(2300.0, "sell", 0.15)
    assert price == 2300.15  # 2300 + 0.15


def test_apply_entry_slippage_buy(tmp_path):
    """Buy entry: slippage makes price higher (worse for buyer)."""
    price = _apply_entry_slippage(2300.0, "buy", 0.15)
    assert price == 2300.15


def test_apply_entry_slippage_sell(tmp_path):
    """Sell entry: slippage makes price lower (worse for seller)."""
    price = _apply_entry_slippage(2300.0, "sell", 0.15)
    assert price == 2299.85


def test_zero_slippage_noop(tmp_path):
    """Zero slippage leaves price unchanged."""
    assert _apply_exit_slippage(2300.0, "buy", 0) == 2300.0
    assert _apply_exit_slippage(2300.0, "sell", 0) == 2300.0
    assert _apply_entry_slippage(2300.0, "buy", 0) == 2300.0
    assert _apply_entry_slippage(2300.0, "sell", 0) == 2300.0


def test_close_position_deducts_commission(tmp_path):
    """_close_position should deduct commission and store net_pnl."""
    _reset_db(tmp_path)

    # Create bot + wallet + position
    from app.multibot.db import default_parameters, json_text
    now = 1700000000
    params = default_parameters()
    params["commission_per_lot"] = 3.5
    params["commission_type"] = "fixed"

    with storage.transaction() as conn:
        conn.execute("INSERT INTO profiles(name,description,enabled,created_at,updated_at) VALUES('test','',1,?,?)", (now, now))
        pid = conn.execute("SELECT id FROM profiles ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.execute(
            "INSERT INTO bots(profile_id,name,strategy_type,strategy_version,symbol,timeframe,enabled,parameters_json,created_at,updated_at) VALUES(?,?,?,?,?,?,1,?,?,?)",
            (pid, "test_bot", "visual", "v1", "XAUUSD", "M15", json_text(params), now, now),
        )
        bid = conn.execute("SELECT id FROM bots ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.execute(
            "INSERT INTO wallets(bot_id,initial_balance,balance,realized_pnl,peak_equity,created_at,updated_at) VALUES(?,10000,10000,0,10000,?,?)",
            (bid, now, now),
        )
        wid = conn.execute("SELECT id FROM wallets ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.execute(
            "INSERT INTO bot_positions(bot_id,wallet_id,symbol,side,lot,entry,stop_loss,take_profit,status,opened_at,updated_at) VALUES(?,?,?,?,?,?,?,?,'open',?,?)",
            (bid, wid, "XAUUSD", "buy", 1.0, 2300.0, 2290.0, 2320.0, now, now),
        )
        pos_id = conn.execute("SELECT id FROM bot_positions ORDER BY id DESC LIMIT 1").fetchone()[0]
        position = dict(conn.execute("SELECT * FROM bot_positions WHERE id=?", (pos_id,)).fetchone())

        # Close at 2310 with bid=2310, ask=2310.5
        _close_position(conn, position, 2310.0, "tp_hit", now + 100, params, 2310.0, 2310.5)

        closed = dict(conn.execute("SELECT * FROM bot_positions WHERE id=?", (pos_id,)).fetchone())
        wallet = dict(conn.execute("SELECT * FROM wallets WHERE id=?", (wid,)).fetchone())

    # PnL gross = (2310 - 2300) * 1 * 100 = 1000
    # Commission = 1.0 * 3.5 = 3.5
    # Spread cost = (2310.5 - 2310) * 1 * 100 * 0.5 = 25.0
    # Net PnL = 1000 - 3.5 - 25.0 = 971.5
    assert closed["pnl"] == 1000.0, f"gross pnl={closed['pnl']}"
    assert closed["commission"] == 3.5, f"commission={closed['commission']}"
    assert closed["net_pnl"] == 971.5, f"net_pnl={closed['net_pnl']}"
    assert closed["status"] == "closed"
    assert wallet["balance"] == 10971.5, f"balance={wallet['balance']}"
    assert wallet["total_commission"] == 3.5


def test_close_position_spread_cost_tracked(tmp_path):
    """Spread cost should be tracked but not double-deducted."""
    _reset_db(tmp_path)
    from app.multibot.db import default_parameters, json_text
    now = 1700000000
    params = default_parameters()
    params["commission_per_lot"] = 0

    with storage.transaction() as conn:
        conn.execute("INSERT INTO profiles(name,description,enabled,created_at,updated_at) VALUES('test','',1,?,?)", (now, now))
        pid = conn.execute("SELECT id FROM profiles ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.execute(
            "INSERT INTO bots(profile_id,name,strategy_type,strategy_version,symbol,timeframe,enabled,parameters_json,created_at,updated_at) VALUES(?,?,?,?,?,?,1,?,?,?)",
            (pid, "test_bot2", "visual", "v1", "XAUUSD", "M15", json_text(params), now, now),
        )
        bid = conn.execute("SELECT id FROM bots ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.execute(
            "INSERT INTO wallets(bot_id,initial_balance,balance,realized_pnl,peak_equity,created_at,updated_at) VALUES(?,10000,10000,0,10000,?,?)",
            (bid, now, now),
        )
        wid = conn.execute("SELECT id FROM wallets ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.execute(
            "INSERT INTO bot_positions(bot_id,wallet_id,symbol,side,lot,entry,stop_loss,take_profit,status,opened_at,updated_at) VALUES(?,?,?,?,?,?,?,?,'open',?,?)",
            (bid, wid, "XAUUSD", "sell", 1.0, 2300.0, 2310.0, 2290.0, now, now),
        )
        pos_id = conn.execute("SELECT id FROM bot_positions ORDER BY id DESC LIMIT 1").fetchone()[0]
        position = dict(conn.execute("SELECT * FROM bot_positions WHERE id=?", (pos_id,)).fetchone())

        # Close at 2295 with bid=2295, ask=2295.3
        _close_position(conn, position, 2295.0, "tp_hit", now + 100, params, 2295.0, 2295.3)

        closed = dict(conn.execute("SELECT * FROM bot_positions WHERE id=?", (pos_id,)).fetchone())

    # PnL gross = (2295 - 2300) * (-1) * 1 * 100 = 500
    # Commission = 0
    # Spread cost = (2295.3 - 2295) * 1 * 100 * 0.5 = 15
    # Net PnL = 500 - 0 - 15 = 485
    assert closed["pnl"] == 500.0
    assert closed["spread_cost"] == pytest.approx(15.0, rel=1e-9)
    assert closed["net_pnl"] == pytest.approx(485.0, rel=1e-9)


def test_manual_open_close_costs(tmp_path):
    """Manual open_position and close_position should apply costs."""
    _reset_db(tmp_path)
    now = 1700000000
    from app.multibot.db import default_parameters, json_text
    params = default_parameters()
    params["commission_per_lot"] = 3.5
    params["slippage_sigma"] = 0.001  # tiny sigma for deterministic test

    with storage.transaction() as conn:
        conn.execute("INSERT INTO profiles(name,description,enabled,created_at,updated_at) VALUES('test','',1,?,?)", (now, now))
        pid = conn.execute("SELECT id FROM profiles ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.execute(
            "INSERT INTO bots(profile_id,name,strategy_type,strategy_version,symbol,timeframe,enabled,parameters_json,created_at,updated_at) VALUES(?,?,?,?,?,?,1,?,?,?)",
            (pid, "manual_bot", "visual", "v1", "XAUUSD", "M15", json_text(params), now, now),
        )
        bid = conn.execute("SELECT id FROM bots ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.execute(
            "INSERT INTO wallets(bot_id,initial_balance,balance,realized_pnl,peak_equity,created_at,updated_at) VALUES(?,10000,10000,0,10000,?,?)",
            (bid, now, now),
        )

    tick = {"bid": 2300.0, "ask": 2300.5, "symbol": "XAUUSD", "timestamp": now}

    opened = open_position(bid, "buy", 1.0, 2290.0, 2320.0, tick)
    assert opened is not None
    assert opened["status"] == "open"
    assert "execution_detail" in opened

    close_tick = {"bid": 2310.0, "ask": 2310.5, "symbol": "XAUUSD", "timestamp": now + 100}
    closed = close_position(bid, close_tick, "manual_test")
    assert closed is not None
    assert closed["status"] == "closed"
    assert closed["commission"] == 3.5
    assert closed["net_pnl"] is not None

    stats = bot_stats_summary(bid)
    assert stats["total_commission"] > 0
    assert stats["closed_trades"] == 1


def test_execution_detail_json_format(tmp_path):
    """execution_detail should be valid JSON with expected keys."""
    _reset_db(tmp_path)
    from app.multibot.db import default_parameters, json_text
    now = 1700000000
    params = default_parameters()

    with storage.transaction() as conn:
        conn.execute("INSERT INTO profiles(name,description,enabled,created_at,updated_at) VALUES('test','',1,?,?)", (now, now))
        pid = conn.execute("SELECT id FROM profiles ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.execute(
            "INSERT INTO bots(profile_id,name,strategy_type,strategy_version,symbol,timeframe,enabled,parameters_json,created_at,updated_at) VALUES(?,?,?,?,?,?,1,?,?,?)",
            (pid, "det_bot", "visual", "v1", "XAUUSD", "M15", json_text(params), now, now),
        )
        bid = conn.execute("SELECT id FROM bots ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.execute(
            "INSERT INTO wallets(bot_id,initial_balance,balance,realized_pnl,peak_equity,created_at,updated_at) VALUES(?,10000,10000,0,10000,?,?)",
            (bid, now, now),
        )
        wid = conn.execute("SELECT id FROM wallets ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.execute(
            "INSERT INTO bot_positions(bot_id,wallet_id,symbol,side,lot,entry,stop_loss,take_profit,status,opened_at,updated_at) VALUES(?,?,?,?,?,?,?,?,'open',?,?)",
            (bid, wid, "XAUUSD", "buy", 1.0, 2300.0, 2290.0, 2320.0, now, now),
        )
        pos_id = conn.execute("SELECT id FROM bot_positions ORDER BY id DESC LIMIT 1").fetchone()[0]
        position = dict(conn.execute("SELECT * FROM bot_positions WHERE id=?", (pos_id,)).fetchone())

        _close_position(conn, position, 2310.0, "tp_hit", now + 100, params, 2310.0, 2310.5)

        closed = dict(conn.execute("SELECT * FROM bot_positions WHERE id=?", (pos_id,)).fetchone())

    import json
    detail = json.loads(closed["execution_detail"])
    assert "commission" in detail
    assert "slippage_pips" in detail
    assert "spread_cost" in detail
    assert "exit_price_raw" in detail
    assert "exit_price_adj" in detail
    assert "pnl_gross" in detail
    assert "pnl_net" in detail
