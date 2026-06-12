from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    bot_id: Optional[int] = None
    strategy_type: str = "trend_ob"
    parameters: dict[str, Any] = {}
    symbol: str = "XAUUSD"
    timeframe: str = "M15"
    start_time: int = Field(gt=0)
    end_time: int = Field(gt=0)
    initial_balance: float = 10000.0


class OptimizeRequest(BaseModel):
    strategy_type: str = "trend_ob"
    param_ranges: dict[str, list[Any]] = Field(default_factory=dict)
    symbol: str = "XAUUSD"
    timeframe: str = "M15"
    start_time: int = Field(gt=0)
    end_time: int = Field(gt=0)
    initial_balance: float = 10000.0
    optimization_metric: Literal["sharpe_ratio", "profit_factor", "net_pnl", "total_r", "win_rate"] = "sharpe_ratio"
