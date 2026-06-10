from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class TickPayload(BaseModel):
    type: Literal["tick", "heartbeat"] = "tick"
    symbol: str = Field(default="XAUUSD")
    bid: float
    ask: float
    timestamp: int
    seq: Optional[int] = None

    @model_validator(mode="after")
    def validate_prices(self):
        if self.bid <= 0 or self.ask <= 0:
            raise ValueError("bid/ask must be positive")
        if self.ask < self.bid:
            raise ValueError("ask must be >= bid")
        return self


class OpenOrderRequest(BaseModel):
    side: Literal["buy", "sell"]
    lot: float = Field(gt=0)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    note: str = "manual"


class CloseOrderRequest(BaseModel):
    note: str = "manual_close"


class ResetRequest(BaseModel):
    balance: Optional[float] = None
