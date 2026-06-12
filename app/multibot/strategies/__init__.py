from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class StrategyMeta:
    id: str
    name: str
    description: str
    decide: Callable
    default_params: dict[str, Any] = field(default_factory=dict)


REGISTRY: dict[str, StrategyMeta] = {}


def register(meta: StrategyMeta) -> None:
    REGISTRY[meta.id] = meta


def get_strategy(strategy_id: str) -> StrategyMeta | None:
    return REGISTRY.get(strategy_id)


def list_strategies() -> list[dict[str, str]]:
    return [
        {"id": s.id, "name": s.name, "description": s.description}
        for s in REGISTRY.values()
    ]


from . import trend_ob as _trend_ob
from . import ma_cross as _ma_cross
from . import rsi_meanrev as _rsi_meanrev
from . import macd_cross as _macd_cross
from . import bb_breakout as _bb_breakout

register(StrategyMeta(
    id="trend_ob",
    name="Trend + OB Retest",
    description="Enter on retest of strong order blocks in trend direction. Uses M15 order blocks with trend filtering.",
    decide=_trend_ob.decide,
))
register(StrategyMeta(
    id="ma_cross",
    name="MA Crossover",
    description="Trade on MA60/MA80 crossover signals. SL/TP sized by ATR.",
    decide=_ma_cross.decide,
))
register(StrategyMeta(
    id="rsi_meanrev",
    name="RSI Mean Reversion",
    description="Buy when RSI exits oversold, sell when RSI exits overbought. Optional trend filter + OB zones.",
    decide=_rsi_meanrev.decide,
))
register(StrategyMeta(
    id="macd_cross",
    name="MACD Crossover",
    description="BUY when MACD crosses above Signal, SELL when MACD crosses below Signal. Uses OB zones for entry.",
    decide=_macd_cross.decide,
))
register(StrategyMeta(
    id="bb_breakout",
    name="Bollinger Breakout",
    description="BUY when close breaks above upper band, SELL when close breaks below lower band. Momentum-following.",
    decide=_bb_breakout.decide,
))
