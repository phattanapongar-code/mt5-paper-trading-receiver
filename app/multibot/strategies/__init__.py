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
    description="Buy when RSI exits oversold (<30), sell when RSI exits overbought (>70). Mean-reversion approach, opposes the trend.",
    decide=_rsi_meanrev.decide,
))
