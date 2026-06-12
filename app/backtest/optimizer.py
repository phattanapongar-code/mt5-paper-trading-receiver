from __future__ import annotations

from itertools import product
from typing import Any

from app.backtest.models import BacktestRequest, OptimizeRequest
from app.backtest.engine import BacktestEngine


class ParameterOptimizer:
    def __init__(self, config: OptimizeRequest):
        self.config = config

    def run(self) -> dict[str, Any]:
        param_names = list(self.config.param_ranges.keys())
        param_values = list(self.config.param_ranges.values())
        combinations = list(product(*param_values))
        total = len(combinations)
        results: list[dict[str, Any]] = []

        for i, combo in enumerate(combinations):
            params = dict(zip(param_names, combo))

            bt_config = BacktestRequest(
                strategy_type=self.config.strategy_type,
                parameters=params,
                symbol=self.config.symbol,
                timeframe=self.config.timeframe,
                start_time=self.config.start_time,
                end_time=self.config.end_time,
                initial_balance=self.config.initial_balance,
            )

            engine = BacktestEngine(bt_config)
            report = engine.run()

            results.append({
                **params,
                "total_trades": report.get("total_trades", 0),
                "win_rate": report.get("win_rate", 0),
                "net_pnl": report.get("net_pnl", 0),
                "profit_factor": report.get("profit_factor", 0),
                "sharpe_ratio": report.get("sharpe_ratio", 0),
                "max_drawdown_pct": report.get("max_drawdown_pct", 0),
                "avg_r": report.get("avg_r", 0),
                "total_r": report.get("total_r", 0),
            })

        metric = self.config.optimization_metric
        results.sort(key=lambda r: r.get(metric, 0), reverse=True)

        return {
            "ok": True,
            "strategy_type": self.config.strategy_type,
            "param_ranges": self.config.param_ranges,
            "total_combinations": total,
            "optimization_metric": metric,
            "results": results,
        }
