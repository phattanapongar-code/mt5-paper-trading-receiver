from app.indicators import compute_indicators


def make_candles(n: int):
    return [
        {"open": float(i), "high": float(i) + 1, "low": float(i) - 1, "close": float(i) + 0.5, "is_closed": 1}
        for i in range(1, n + 1)
    ]


def test_warming_up_before_ma300():
    result = compute_indicators(make_candles(100))
    assert result["trend"] == "WARMING_UP"
    assert result["ready_for_ma300"] is False


def test_bullish_ma_stack_after_300_candles():
    result = compute_indicators(make_candles(320))
    assert result["ready_for_ma300"] is True
    assert result["trend"] == "BULLISH"
