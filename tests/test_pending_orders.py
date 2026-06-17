from __future__ import annotations

from pathlib import Path

from app import storage
from app.config import settings
from app.multibot.db import migrate, json_text, default_parameters
from app.multibot.runtime import _evaluate_bot, _trend
from app.indicators import compute_indicators


def _reset_db(tmp_path: Path) -> None:
    if storage._conn is not None:
        storage._conn.close()
    storage._conn = None
    object.__setattr__(settings, "db_path", str(tmp_path / "pending.sqlite3"))
    storage.init_db()


def _insert_closed(open_time: int, close: float) -> None:
    storage.execute(
        """
        INSERT INTO candles(symbol, timeframe, open_time, close_time, open, high, low, close, tick_count, is_closed, updated_at)
        VALUES ('XAUUSD', 'M15', ?, ?, ?, ?, ?, ?, 10, 1, ?)
        """,
        (open_time, open_time + 900, close - 0.2, close + 0.5, close - 0.5, close, open_time + 900),
    )


def _seed_bearish(tmp_path: Path) -> None:
    _reset_db(tmp_path)
    # Falling closes force BEARISH MA alignment once 320 closed candles exist.
    for i in range(320):
        _insert_closed(i * 900, 500.0 - i)
    # Verify trend is BEARISH before running tests
    trend = _trend("XAUUSD", "M15")
    assert trend == "BEARISH", f"Expected BEARISH trend, got {trend}"


def test_trend_detection_works(tmp_path):
    _seed_bearish(tmp_path)
    trend = _trend("XAUUSD", "M15")
    assert trend == "BEARISH"


def test_trend_returns_warming_up_without_enough_data(tmp_path):
    _reset_db(tmp_path)
    for i in range(100):
        _insert_closed(i * 900, 500.0 - i)
    trend = _trend("XAUUSD", "M15")
    assert trend == "WARMING_UP"


def test_stages_one_aligned_pending_after_zone_touch(tmp_path):
    _seed_bearish(tmp_path)
    import json
    from app.multibot.visual_engine import execute_graph
    from app.multibot.visual_router import ensure_table
    # Latest candle open_time after 320 inserts at 900s intervals is 319*900 = 287100
    # break_open_time must be within 20 candles (ob_max_age_candles default) of the latest candle
    recent_break = 287100 - 5 * 900  # 5 candles ago
    storage.execute(
        """
        INSERT INTO order_blocks(
            symbol, timeframe, side, bos_id, swing_open_time, swing_price,
            break_open_time, break_close, ob_open_time, ob_open, ob_close,
            ob_low, ob_high, impulse_body, impulse_range, impulse_body_ratio,
            impulse_range_ratio, origin_swing_open_time, origin_swing_price,
            swing_distance_ratio, retest_count, status, score, is_strong,
            score_reasons, created_at, updated_at
        ) VALUES ('XAUUSD','M15','bearish',1,1,200,?,190,3,181,182,180,184,5,6,2,2,3,184,0,0,'active',8,1,'test',1,1)
        """,
        (recent_break,),
    )
    # Set up a bot to evaluate
    migrate()
    ensure_table()

    # Create a visual strategy graph that processes bearish OB
    graph = {
        "nodes": [
            {"id": "price_1", "type": "price", "data": {"params": {"value": "mid"}, "label": "Price"}},
            {"id": "ob_1", "type": "ob_query", "data": {"params": {"side": "sell", "min_score": 6}, "label": "OB Query"}},
            {"id": "age_1", "type": "ob_not_stale", "data": {"params": {"max_age_candles": 20}, "label": "Not Stale"}},
            {"id": "range_1", "type": "ob_in_range", "data": {"params": {}, "label": "In Range"}},
            {"id": "order_1", "type": "order", "data": {"params": {"side": "sell", "entry_style": "ob_boundary", "risk_percent": 1.0, "sl_atr_multiplier": 1.5, "tp_r_multiple": 2.0, "atr_period": 14}, "label": "Order"}},
        ],
        "edges": [
            {"source": "ob_1", "target": "range_1"},
            {"source": "price_1", "target": "range_1"},
            {"source": "ob_1", "target": "age_1"},
            {"source": "age_1", "target": "order_1"},
            {"source": "range_1", "target": "order_1"},
            {"source": "ob_1", "target": "order_1"},
        ],
    }

    now = int(__import__("time").time())
    storage.execute(
        "INSERT INTO visual_strategies(name, description, graph_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        ("test_bearish_ob", "", json.dumps(graph), now, now),
    )
    vs_id = storage.query_one("SELECT id FROM visual_strategies WHERE name='test_bearish_ob'")["id"]

    existing = storage.query_one("SELECT id FROM bots WHERE name='Paper Trading'")
    assert existing is not None, "Paper Trading bot should exist after migrate"
    bot_id = existing["id"]

    # Assign the visual strategy to the bot
    storage.execute("UPDATE bots SET visual_strategy_id=?, strategy_type='visual' WHERE id=?", (vs_id, bot_id))

    # Enable the bot
    storage.execute(f"UPDATE bots SET enabled=1 WHERE id={bot_id}")
    storage.execute("UPDATE profiles SET enabled=1 WHERE id=1")

    # Process a tick that touches the OB zone (180-184)
    from app.multibot.runtime import process_tick_sync
    result = process_tick_sync({
        "type": "tick", "symbol": "XAUUSD", "bid": 182.0, "ask": 182.2,
        "timestamp": int(__import__("time").time()), "seq": 1
    })
    assert result["processed_bots"] >= 1

    # Check that a pending order was created
    pending = storage.query_one(f"SELECT * FROM bot_pending_orders WHERE bot_id={bot_id} AND status='pending' ORDER BY id DESC LIMIT 1")
    assert pending is not None
    assert pending["side"] == "sell"
    # Entry is at OB low (bearish entry = ob_low)
    assert pending["entry"] == 180.0


def test_rr_gate_rejects_low_rr(tmp_path):
    _seed_bearish(tmp_path)
    from app.multibot.runtime import process_tick_sync
    from app.multibot.service import update_bot_parameters
    
    recent_break = 287100 - 5 * 900
    storage.execute(
        """
        INSERT INTO order_blocks(
            symbol, timeframe, side, bos_id, swing_open_time, swing_price,
            break_open_time, break_close, ob_open_time, ob_open, ob_close,
            ob_low, ob_high, impulse_body, impulse_range, impulse_body_ratio,
            impulse_range_ratio, origin_swing_open_time, origin_swing_price,
            swing_distance_ratio, retest_count, status, score, is_strong,
            score_reasons, created_at, updated_at
        ) VALUES ('XAUUSD','M15','bearish',1,1,200,?,190,3,181,182,180,184,5,6,2,2,3,184,0,0,'active',8,1,'test',1,1)
        """,
        (recent_break,),
    )
    migrate()
    storage.execute("UPDATE bots SET enabled=1 WHERE id=1")

    # Lower tp_r_multiple to get rejected
    update_bot_parameters(1, {"tp_r_multiple": 1.0, "min_rr": 1.5})

    result = process_tick_sync({
        "type": "tick", "symbol": "XAUUSD", "bid": 182.0, "ask": 182.2,
        "timestamp": int(__import__("time").time()), "seq": 1
    })
    # Should still process but no pending created due to low RR
    # Check signal logs for rejection
    rejection = storage.query_one(
        "SELECT * FROM bot_signal_logs WHERE bot_id=1 AND event_type='pending_created' ORDER BY id DESC LIMIT 1"
    )
    assert rejection is None, "Should not have created a pending order with low RR"
