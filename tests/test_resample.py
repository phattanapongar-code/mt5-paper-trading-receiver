from app.candle_engine import CandleEngine


def test_bucket_aligns_to_timeframe():
    assert CandleEngine._bucket(901, 900) == 900
    assert CandleEngine._bucket(3599, 3600) == 0


def test_m1_history_shape_documentation():
    row = {
        "open_time": 60,
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "tick_volume": 10,
    }
    assert row["high"] >= max(row["open"], row["close"], row["low"])
