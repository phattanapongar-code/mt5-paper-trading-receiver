from __future__ import annotations

from pathlib import Path

from app import storage
from app.config import settings
from app.multibot.db import migrate
from app.multibot.runtime import process_tick_sync


def _reset_db(tmp_path: Path) -> None:
    if storage._conn is not None:
        storage._conn.close()
    storage._conn = None
    object.__setattr__(settings, "db_path", str(tmp_path / "final.sqlite3"))
    storage.init_db()


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
    from app.replay import ReplayEngine
    result = ReplayEngine().run("XAUUSD")
    assert result["mode"] == "RESEARCH_PREVIEW_NOT_TICK_PERFECT"
    assert result["simulated"] == 1
    assert result["wins"] == 1
    assert result["losses"] == 0
    assert result["net_r"] == 2.0
    assert ReplayEngine().latest("XAUUSD") is not None
