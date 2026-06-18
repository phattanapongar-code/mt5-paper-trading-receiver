from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app import storage

logger = logging.getLogger(__name__)


def _bot_report(bot_id: int, bot_name: str, day: str) -> str | None:
    from app.multibot.service import _decode
    start = int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    end = start + 86400

    trades = storage.query_all(
        "SELECT * FROM bot_positions WHERE bot_id=? AND status='closed' AND closed_at>=? AND closed_at<? ORDER BY closed_at ASC",
        (bot_id, start, end),
    )
    if not trades:
        return None

    total = len(trades)
    gross_pnls = [float(t.get("pnl") or 0.0) for t in trades]
    net_pnls = [float(t.get("net_pnl") or t.get("pnl") or 0.0) for t in trades]
    rs = [float(t.get("r_multiple") or 0.0) for t in trades if t.get("r_multiple")]
    wins = [p for p in net_pnls if p > 0]
    losses = [p for p in net_pnls if p < 0]
    win_rate = len(wins) / total * 100 if total else 0.0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None

    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in net_pnls:
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)

    total_comm = sum(float(t.get("commission") or 0.0) for t in trades)
    total_slip = sum(abs(float(t.get("slippage") or 0.0)) for t in trades)

    avg_r = sum(rs) / len(rs) if rs else 0.0
    avg_r_str = f"{avg_r:+.2f}R" if avg_r >= 0 else f"{avg_r:.2f}R"

    wallet = storage.query_one("SELECT balance FROM wallets WHERE bot_id=?", (bot_id,))
    balance = float(wallet["balance"]) if wallet else 0.0

    return (
        f"\U0001f4c5 <b>Daily Report - {bot_name}</b> ({day})\n"
        f"Trades: {total} | Win: {len(wins)} ({win_rate:.0f}%) | Loss: {len(losses)}\n"
        f"Gross PnL: <b>{sum(gross_pnls):+.2f}</b>\n"
        f"Net PnL: <b>{sum(net_pnls):+.2f}</b>\n"
        + (f"Profit Factor: {profit_factor:.2f}\n" if profit_factor else "") +
        f"Avg R: {avg_r_str}\n"
        f"Max DD: ${max_dd:.2f}\n"
        f"Commission: ${total_comm:.2f} | Slippage: {total_slip:.2f} pts\n"
        f"Balance: ${balance:.2f}"
    )


def generate_daily_reports() -> list[str]:
    day = datetime.now(timezone.utc).date().isoformat()
    bots = storage.query_all("SELECT id, name FROM bots ORDER BY id") or []
    messages: list[str] = []
    for bot in bots:
        msg = _bot_report(int(bot["id"]), str(bot["name"]), day)
        if msg:
            messages.append(msg)
    return messages


def send_report_date(day: str) -> str:
    return f"report.{day}"
