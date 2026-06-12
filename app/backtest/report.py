from __future__ import annotations

import statistics
from typing import Any


def generate_report(trades: list[dict[str, Any]], equity_curve: list[dict[str, Any]], initial_balance: float) -> dict[str, Any]:
    if not trades:
        return {
            "ok": True,
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "profit_factor": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "avg_r": 0.0,
            "total_r": 0.0,
            "final_balance": round(initial_balance, 2),
            "return_pct": 0.0,
            "equity_curve": equity_curve,
            "trades": [],
        }

    wins = [t for t in trades if t.get("pnl", 0) > 0]
    losses = [t for t in trades if t.get("pnl", 0) <= 0]
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    net_pnl = sum(t["pnl"] for t in trades)
    win_rate = len(wins) / len(trades) if trades else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)

    # Sharpe ratio (per-trade returns as % of balance)
    returns = [t["pnl"] / initial_balance for t in trades]
    if len(returns) > 1 and statistics.stdev(returns) > 0:
        sharpe = (statistics.mean(returns) / statistics.stdev(returns)) * (252 ** 0.5)
    else:
        sharpe = 0.0 if net_pnl <= 0 else 1.0

    # Max drawdown from equity curve
    peak = -float("inf")
    max_dd = 0.0
    for point in equity_curve:
        eq = point.get("equity", 0)
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    r_values = [t.get("r_multiple", 0) for t in trades if t.get("r_multiple")]
    avg_r = statistics.mean(r_values) if r_values else 0
    total_r = sum(r_values)

    final_balance = equity_curve[-1]["equity"] if equity_curve else initial_balance + net_pnl
    return_pct = ((final_balance - initial_balance) / initial_balance) * 100 if initial_balance > 0 else 0

    return {
        "ok": True,
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 4),
        "net_pnl": round(net_pnl, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": round(profit_factor, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "avg_r": round(avg_r, 2),
        "total_r": round(total_r, 2),
        "final_balance": round(final_balance, 2),
        "return_pct": round(return_pct, 2),
        "equity_curve": equity_curve,
        "trades": trades[-100:],
    }
