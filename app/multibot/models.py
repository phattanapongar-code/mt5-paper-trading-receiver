from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    name: str
    description: str = ""
    enabled: bool = True


class BotCreate(BaseModel):
    profile_id: int
    name: str
    visual_strategy_id: Optional[int] = None
    symbol: str = "XAUUSD"
    timeframe: str = "M15"
    enabled: bool = False
    initial_balance: float = Field(default=500.0, gt=0)
    parameters: dict[str, Any] = {}


class CloneBotRequest(BaseModel):
    name: str


class WalletResetRequest(BaseModel):
    balance: float = Field(gt=0)


class BotParameterUpdate(BaseModel):
    parameters: dict[str, Any]


class RenameBotRequest(BaseModel):
    name: str


class UpdateBotRequest(BaseModel):
    name: str | None = None
    visual_strategy_id: int | None = None
    symbol: str | None = None
    timeframe: str | None = None
    enabled: bool | None = None
    initial_balance: float | None = None
