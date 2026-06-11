from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app import storage


def _closed_trades() -> list[dict[str, Any]]:
    return storage.query_all("SELECT * FROM bot_positions WHERE bot_id=1 AND status='closed' ORDER BY closed_at ASC, id ASC")


class StatsEngine:
    def summary(self) -> dict[str, Any]:
        closed = _closed_trades()
        pnls = [float(t.get("pnl") or 0.0) for t in closed]
        rs = [float(t.get("r_multiple") or 0.0) for t in closed if t.get("r_multiple") is not None]
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
        wallet = storage.query_one("SELECT * FROM wallets WHERE bot_id=1") or {}
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
            "balance": float(wallet.get("balance") or 0.0),
            "realized_pnl": float(wallet.get("realized_pnl") or 0.0),
        }

    def equity_curve(self) -> list[tuple[int, float]]:
        closed = storage.query_all(
            "SELECT closed_at, pnl FROM bot_positions WHERE bot_id=1 AND status='closed' AND closed_at IS NOT NULL ORDER BY closed_at ASC, id ASC"
        )
        result: list[tuple[int, float]] = []
        cum = 0.0
        for row in closed:
            cum += float(row["pnl"] or 0.0)
            result.append((int(row["closed_at"]), round(cum, 2)))
        return result

    def pnl_by_day(self) -> list[tuple[int, float]]:
        closed = storage.query_all(
            "SELECT closed_at, pnl FROM bot_positions WHERE bot_id=1 AND status='closed' AND closed_at IS NOT NULL ORDER BY closed_at ASC"
        )
        daily: dict[str, float] = {}
        for row in closed:
            dt = datetime.fromtimestamp(int(row["closed_at"]), tz=timezone.utc)
            day_key = dt.strftime("%Y-%m-%d")
            daily[day_key] = daily.get(day_key, 0.0) + float(row["pnl"] or 0.0)
        result: list[tuple[int, float]] = []
        for day_key in sorted(daily):
            ts = int(datetime.strptime(day_key, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
            result.append((ts, round(daily[day_key], 2)))
        return result
