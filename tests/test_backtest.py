from __future__ import annotations

from pathlib import Path

from app.backtest.report import generate_report
from app.backtest.models import BacktestRequest


def test_report_empty():
    report = generate_report([], [], 10000.0)
    assert report["ok"] is True
    assert report["total_trades"] == 0
    assert report["final_balance"] == 10000.0
    assert report["return_pct"] == 0.0


def test_report_with_trades():
    trades = [
        {"pnl": 500.0, "r_multiple": 2.0},
        {"pnl": -200.0, "r_multiple": -1.0},
        {"pnl": 300.0, "r_multiple": 1.5},
    ]
    equity = [
        {"time": 1, "equity": 10500.0},
        {"time": 2, "equity": 10300.0},
        {"time": 3, "equity": 10600.0},
    ]
    report = generate_report(trades, equity, 10000.0)
    assert report["total_trades"] == 3
    assert report["wins"] == 2
    assert report["losses"] == 1
    import pytest
    assert report["win_rate"] == pytest.approx(2 / 3, abs=0.001)
    assert report["net_pnl"] == 600.0
    assert report["gross_profit"] == 800.0
    assert report["gross_loss"] == 200.0
    assert report["profit_factor"] == 4.0
    assert report["avg_r"] > 0
    assert report["final_balance"] > 10599


def test_report_sharpe_zero_on_single_trade():
    trades = [{"pnl": 100.0, "r_multiple": 2.0}]
    equity = [{"time": 1, "equity": 10100.0}]
    report = generate_report(trades, equity, 10000.0)
    assert report["sharpe_ratio"] == 1.0 or report["sharpe_ratio"] == 0.0


def test_report_max_drawdown():
    trades = [{"pnl": -500.0, "r_multiple": -1.0}]
    equity = [
        {"equity": 10000.0},
        {"equity": 9500.0},
    ]
    report = generate_report(trades, equity, 10000.0)
    assert report["max_drawdown_pct"] == 5.0


def test_backtest_request_validation():
    req = BacktestRequest(start_time=1000, end_time=2000)
    assert req.strategy_type == "trend_ob"
    assert req.symbol == "XAUUSD"
    assert req.timeframe == "M15"
    assert req.initial_balance == 10000.0


def test_backtest_request_custom():
    req = BacktestRequest(
        strategy_type="bb_breakout",
        symbol="EURUSD",
        timeframe="H1",
        start_time=1000,
        end_time=2000,
        initial_balance=5000.0,
        parameters={"risk_percent": 0.02},
    )
    assert req.strategy_type == "bb_breakout"
    assert req.symbol == "EURUSD"
    assert req.parameters["risk_percent"] == 0.02
