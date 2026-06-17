from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    bot_id: Optional[int] = None
    visual_strategy_id: Optional[int] = None
    graph: Optional[dict[str, Any]] = None
    parameters: dict[str, Any] = {}
    symbol: str = "XAUUSD"
    timeframe: str = "M15"
    start_time: int = Field(gt=0)
    end_time: int = Field(gt=0)
    initial_balance: float = 10000.0
    # Optimizer fields (optional, only used by ParameterOptimizer)
    param_ranges: dict[str, list[Any]] = Field(default_factory=dict)
    optimization_metric: Literal["sharpe_ratio", "profit_factor", "net_pnl", "total_r", "win_rate"] = "sharpe_ratio"
