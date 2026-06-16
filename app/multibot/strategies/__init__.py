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

register(StrategyMeta(
    id="trend_ob",
    name="Trend + OB Retest",
    description="Enter on retest of strong order blocks in trend direction. Uses M15 order blocks with trend filtering.",
    decide=_trend_ob.decide,
))

from . import bb_breakout as _bb_breakout

register(StrategyMeta(
    id="bb_breakout",
    name="BB Breakout",
    description="Bollinger Band breakout — BUY when close breaks above upper BB, SELL when close breaks below lower BB. Uses OB zones or ATR fallback.",
    decide=_bb_breakout.decide,
))

from . import ma_cross as _ma_cross

register(StrategyMeta(
    id="ma_cross",
    name="MA Cross",
    description="MA Crossover — BUY when MA60 crosses above MA80, SELL when MA60 crosses below MA80. ATR-based SL/TP.",
    decide=_ma_cross.decide,
))

from . import macd_cross as _macd_cross

register(StrategyMeta(
    id="macd_cross",
    name="MACD Cross",
    description="MACD Crossover — BUY when MACD crosses above Signal line, SELL when MACD crosses below. Uses OB zones or ATR fallback.",
    decide=_macd_cross.decide,
))

from . import rsi_meanrev as _rsi_meanrev

register(StrategyMeta(
    id="rsi_meanrev",
    name="RSI Mean Reversion",
    description="RSI Mean Reversion — BUY when RSI exits oversold, SELL when RSI exits overbought. Optional trend filter + OB zones.",
    decide=_rsi_meanrev.decide,
))

from . import visual as _visual

register(StrategyMeta(
    id="visual",
    name="Visual Strategy",
    description="Node-graph strategy built with the visual drag-and-drop editor.",
    decide=_visual.decide,
))
