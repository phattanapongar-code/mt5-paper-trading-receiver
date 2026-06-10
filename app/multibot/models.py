from typing import Any
from pydantic import BaseModel, Field

class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    enabled: bool = True

class BotCreate(BaseModel):
    profile_id: int
    name: str = Field(min_length=1, max_length=100)
    strategy_type: str = "trend_ob"
    strategy_version: str = "v1"
    symbol: str = "XAUUSD"
    timeframe: str = "M15"
    enabled: bool = False
    initial_balance: float = Field(default=500.0, gt=0)
    parameters: dict[str, Any] | None = None

class CloneBotRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)

class WalletResetRequest(BaseModel):
    balance: float = Field(default=500.0, gt=0)
