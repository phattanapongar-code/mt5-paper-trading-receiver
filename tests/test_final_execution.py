from __future__ import annotations

from pathlib import Path

from app import storage
from app.execution import AutoPaperExecutionEngine
from app.paper_engine import PaperEngine
from app.pending_orders import PendingOrderEngine
from app.replay import ReplayEngine
from app.stats import StatsEngine


def _reset_db(tmp_path: Path) -> None:
    if storage._conn is not None:
        storage._conn.close()
    storage._conn = None
    object.__setattr__(storage.settings, "db_path", str(tmp_path / "final.sqlite3"))
    storage.init_db()


def _insert_pending_sell() -> None:
    storage.execute(
        """
        INSERT INTO pending_orders(
            symbol, timeframe, side, ob_id, ob_side, ob_break_open_time,
            source_trend, entry, stop_loss, take_profit, risk_distance,
            risk_reward, spread_at_creation, created_open_time,
            expires_open_time, status, created_at, updated_at
        ) VALUES ('XAUUSD','M15','sell',1,'bearish',100,'BEARISH',182.0,185.2,175.6,3.2,2.0,0.2,100,7300,'pending',100,100)
        """
    )


def test_auto_fill_then_tp_updates_account_and_stats(tmp_path):
    _reset_db(tmp_path)
    _insert_pending_sell()
    paper = PaperEngine()
    pending = PendingOrderEngine(timeframe="M15")
    execution = AutoPaperExecutionEngine(paper, pending)
    execution.set_enabled(True)

    filled = execution.on_tick("XAUUSD", bid=182.1, ask=182.2)
    assert filled is not None
    assert filled["event"] == "auto_paper_filled"
    assert filled["pending_order"]["status"] == "filled"
    assert filled["trade"]["status"] == "open"
    assert filled["trade"]["lot"] == 0.01

    closed = paper.on_tick(bid=175.4, ask=175.5)
    assert closed is not None
    assert closed["status"] == "closed"
    assert closed["exit_reason"] == "tp_hit"
    assert closed["pnl"] > 0
    assert closed["r_multiple"] > 0

    summary = StatsEngine().summary()
    assert summary["closed_trades"] == 1
    assert summary["wins"] == 1
    assert summary["losses"] == 0
    assert summary["net_pnl"] > 0


def _insert_ob() -> None:
    storage.execute(
        """
        INSERT INTO order_blocks(
            symbol,timeframe,side,bos_id,swing_open_time,swing_price,
            break_open_time,break_close,ob_open_time,ob_open,ob_close,
            ob_low,ob_high,impulse_body,impulse_range,impulse_body_ratio,
            impulse_range_ratio,origin_swing_open_time,origin_swing_price,
            swing_distance_ratio,retest_count,status,score,is_strong,
            score_reasons,created_at,updated_at
        ) VALUES ('XAUUSD','M15','bearish',1,0,100,900,95,0,99,100,99,101,3,4,2,2,0,101,0,0,'active',8,1,'test',1,1)
        """
    )


def _insert_m1(open_time: int, low: float, high: float) -> None:
    mid = (low + high) / 2
    storage.execute(
        """
        INSERT INTO candles(symbol,timeframe,open_time,close_time,open,high,low,close,tick_count,is_closed,updated_at)
        VALUES ('XAUUSD','M1',?,?,?,?,?,?,10,1,?)
        """,
        (open_time, open_time + 60, mid, high, low, mid, open_time + 60),
    )


def test_replay_preview_generates_resolved_result(tmp_path):
    _reset_db(tmp_path)
    _insert_ob()
    # Sell OB midpoint is 100, SL 101.6, TP 96.8. First M1 fills, second hits TP.
    _insert_m1(900, 99.8, 100.2)
    _insert_m1(960, 96.7, 99.5)
    result = ReplayEngine().run("XAUUSD")
    assert result["mode"] == "RESEARCH_PREVIEW_NOT_TICK_PERFECT"
    assert result["simulated"] == 1
    assert result["wins"] == 1
    assert result["losses"] == 0
    assert result["net_r"] == 2.0
    assert ReplayEngine().latest("XAUUSD") is not None
