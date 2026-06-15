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
