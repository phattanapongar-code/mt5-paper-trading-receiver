from __future__ import annotations

from pathlib import Path

from app import storage
from app.pending_orders import PendingOrderEngine


def _reset_db(tmp_path: Path) -> None:
    if storage._conn is not None:
        storage._conn.close()
    storage._conn = None
    object.__setattr__(storage.settings, "db_path", str(tmp_path / "pending.sqlite3"))
    storage.init_db()


def _insert_closed(open_time: int, close: float) -> None:
    storage.execute(
        """
        INSERT INTO candles(symbol, timeframe, open_time, close_time, open, high, low, close, tick_count, is_closed, updated_at)
        VALUES ('XAUUSD', 'M15', ?, ?, ?, ?, ?, ?, 10, 1, ?)
        """,
        (open_time, open_time + 900, close - 0.2, close + 0.5, close - 0.5, close, open_time + 900),
    )


def _seed_bearish(tmp_path: Path) -> PendingOrderEngine:
    _reset_db(tmp_path)
    # Falling closes force BEARISH MA alignment once 320 closed candles exist.
    for i in range(320):
        _insert_closed(i * 900, 500.0 - i)
    storage.execute(
        """
        INSERT INTO order_blocks(
            symbol, timeframe, side, bos_id, swing_open_time, swing_price,
            break_open_time, break_close, ob_open_time, ob_open, ob_close,
            ob_low, ob_high, impulse_body, impulse_range, impulse_body_ratio,
            impulse_range_ratio, origin_swing_open_time, origin_swing_price,
            swing_distance_ratio, retest_count, status, score, is_strong,
            score_reasons, created_at, updated_at
        ) VALUES ('XAUUSD','M15','bearish',1,1,200,2,190,3,181,182,180,184,5,6,2,2,3,184,0,0,'active',8,1,'test',1,1)
        """
    )
    return PendingOrderEngine(timeframe="M15", expiry_candles=8, min_rr=1.5, tp_r_multiple=2.0, sl_buffer_ratio=0.30)


def test_stages_one_aligned_pending_after_zone_touch(tmp_path):
    engine = _seed_bearish(tmp_path)
    result = engine.on_tick("XAUUSD", bid=182.0, ask=182.2, received_at=int(__import__("time").time()))
    created = result["created"]
    assert created is not None
    assert created["side"] == "sell"
    assert created["entry"] == 182.0
    assert created["stop_loss"] == 185.2
    assert round(created["take_profit"], 6) == 175.6
    assert created["risk_reward"] == 2.0
    assert engine.state("XAUUSD")["counts"]["pending"] == 1


def test_cancels_after_eight_m15_candles(tmp_path):
    engine = _seed_bearish(tmp_path)
    created = engine.on_tick("XAUUSD", bid=182.0, ask=182.2, received_at=int(__import__("time").time()))["created"]
    assert created is not None
    expiry = int(created["expires_open_time"])
    _insert_closed(expiry, 170.0)
    cancelled = engine.cancel_if_needed("XAUUSD", bid=170.0, ask=170.2, received_at=int(__import__("time").time()))
    assert cancelled is not None
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancel_reason"] == "expired_after_candles"


def test_rr_gate_rejects_tp_multiple_below_minimum(tmp_path):
    engine = _seed_bearish(tmp_path)
    engine.tp_r_multiple = 1.0
    result = engine.on_tick("XAUUSD", bid=182.0, ask=182.2, received_at=int(__import__("time").time()))
    assert result["created"] is None
    assert result["rejected"]["reason"] == "rr_too_low"



def test_pending_survives_order_block_id_change_after_rebuild(tmp_path):
    engine = _seed_bearish(tmp_path)
    created = engine.on_tick("XAUUSD", bid=182.0, ask=182.2, received_at=int(__import__("time").time()))["created"]
    assert created is not None
    original_ob_id = int(created["ob_id"])
    storage.execute("DELETE FROM order_blocks")
    storage.execute(
        """
        INSERT INTO order_blocks(
            symbol, timeframe, side, bos_id, swing_open_time, swing_price,
            break_open_time, break_close, ob_open_time, ob_open, ob_close,
            ob_low, ob_high, impulse_body, impulse_range, impulse_body_ratio,
            impulse_range_ratio, origin_swing_open_time, origin_swing_price,
            swing_distance_ratio, retest_count, status, score, is_strong,
            score_reasons, created_at, updated_at
        ) VALUES ('XAUUSD','M15','bearish',2,1,200,2,190,3,181,182,180,184,5,6,2,2,3,184,0,0,'active',8,1,'test',2,2)
        """
    )
    rebuilt_ob = storage.query_one("SELECT * FROM order_blocks LIMIT 1")
    assert rebuilt_ob is not None
    assert int(rebuilt_ob["id"]) != original_ob_id
    assert engine.cancel_if_needed("XAUUSD", bid=182.0, ask=182.2, received_at=int(__import__("time").time())) is None
    assert engine.active("XAUUSD") is not None


def test_rejection_logs_are_rate_limited(tmp_path):
    engine = _seed_bearish(tmp_path)
    engine.max_spread = 0.1
    first = engine.on_tick("XAUUSD", bid=182.0, ask=182.2, received_at=int(__import__("time").time()))["rejected"]
    second = engine.on_tick("XAUUSD", bid=182.0, ask=182.2, received_at=int(__import__("time").time()))["rejected"]
    assert first is not None and first["logged"] is True
    assert second is not None and second["logged"] is False
    rows = engine.rejections("XAUUSD")
    assert len(rows) == 1
