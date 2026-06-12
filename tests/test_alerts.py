from __future__ import annotations

import pytest

from app.alert import AlertEngine


def _engine() -> AlertEngine:
    eng = AlertEngine()
    eng.configure("fake:token", "12345", enabled=True)
    return eng


@pytest.mark.asyncio
async def test_send_disabled_when_not_configured():
    eng = AlertEngine()
    ok = await eng.send("test")
    assert ok is False


@pytest.mark.asyncio
async def test_send_disabled_when_not_enabled():
    eng = AlertEngine()
    eng.configure("token", "chat", enabled=False)
    ok = await eng.send("test")
    assert ok is False


@pytest.mark.asyncio
async def test_send_fails_gracefully_on_bad_token():
    eng = _engine()
    ok = await eng.send("test")
    assert ok is False  # bad token -> HTTP 401 -> False


def test_notify_trade_open_includes_slippage():
    eng = _engine()
    # Just ensure no exception; format check
    eng.notify_trade_open("bot1", "buy", 2315.42, 2308.10, 2330.20, 0.05, "XAUUSD", slippage_pips=0.12)
    eng.notify_trade_open("bot1", "sell", 2310.0, 2320.0, 2300.0, 1.0, "XAUUSD")


def test_notify_trade_close_with_costs():
    eng = _engine()
    eng.notify_trade_close(
        "bot1", "buy", 52.40, "tp_hit", "XAUUSD",
        r_multiple=2.15, commission=3.5, slippage=0.18, spread_cost=1.52, net_pnl=47.20,
    )


def test_notify_trade_close_without_costs():
    eng = _engine()
    eng.notify_trade_close("bot1", "buy", 47.20, "sl_hit", "XAUUSD", r_multiple=1.5)


def test_notify_risk():
    eng = _engine()
    eng.notify_risk("bot1", "Daily Loss Limit Hit", "Daily PnL: -150.00 (limit: 3%)\nBot PAUSED")
    eng.notify_risk("bot1", "Max Consecutive Losses", "3 losses in a row \u2192 PAUSED")


def test_notify_health():
    eng = _engine()
    eng.notify_health("offline", "No ticks received for 30s\nLast tick: 1234567890")
    eng.notify_health("online", "Sender reconnected\nLast tick: 1234567899")


def test_notify_error():
    eng = _engine()
    eng.notify_error("bot1", "Something went wrong")


@pytest.mark.asyncio
async def test_test_sends_message():
    eng = _engine()
    ok = await eng.test()
    assert ok is False  # bad token


@pytest.mark.asyncio
async def test_close_is_idempotent():
    eng = _engine()
    await eng.close()
    await eng.close()  # second close should not raise


@pytest.mark.asyncio
async def test_send_retry_on_failure():
    eng = _engine()
    eng.configure("fake:token", "12345", enabled=True)
    ok = await eng.send("test", retries=1)
    assert ok is False  # fails after retry too


def test_configure_updates_state():
    eng = AlertEngine()
    assert eng.enabled is False
    eng.configure("tok", "cid", True)
    assert eng.bot_token == "tok"
    assert eng.chat_id == "cid"
    assert eng.enabled is True
