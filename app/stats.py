from __future__ import annotations

from typing import Any

from app import storage


class StatsEngine:
    def summary(self) -> dict[str, Any]:
        closed = storage.query_all("SELECT * FROM trades WHERE status = 'closed' ORDER BY closed_at ASC, id ASC")
        pnls = [float(t.get("pnl") or 0.0) for t in closed]
        rs = [float(t.get("r_multiple") or 0.0) for t in closed]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0
        for pnl in pnls:
            equity += pnl
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        account = storage.query_one("SELECT * FROM paper_account WHERE id = 1") or {}
        return {
            "closed_trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": len([p for p in pnls if p == 0]),
            "win_rate": (len(wins) / len(closed)) if closed else 0.0,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else None,
            "net_pnl": sum(pnls),
            "average_pnl": (sum(pnls) / len(pnls)) if pnls else 0.0,
            "average_r": (sum(rs) / len(rs)) if rs else 0.0,
            "max_drawdown_usd": max_drawdown,
            "balance": float(account.get("balance") or 0.0),
            "realized_pnl": float(account.get("realized_pnl") or 0.0),
        }
