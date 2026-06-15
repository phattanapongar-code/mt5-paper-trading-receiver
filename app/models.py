from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class CandlePayload(BaseModel):
    timeframe: Literal["M1"] = "M1"
    open_time: int = Field(gt=0)
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    tick_volume: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_ohlc(self):
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be >= open/close/low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be <= open/close/high")
        return self


class TickPayload(BaseModel):
    type: Literal["tick", "heartbeat"] = "tick"
    symbol: str = Field(default="XAUUSD")
    bid: float
    ask: float
    timestamp: int
    seq: Optional[int] = None
    candle: Optional[CandlePayload] = None

    @model_validator(mode="after")
    def validate_prices(self):
        if self.bid <= 0 or self.ask <= 0:
            raise ValueError("bid/ask must be positive")
        if self.ask < self.bid:
            raise ValueError("ask must be >= bid")
        return self


class HistoryCandle(BaseModel):
    open_time: int = Field(gt=0)
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    tick_volume: int = Field(default=0, ge=0)
    source_open_time: Optional[int] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_ohlc(self):
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be >= open/close/low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be <= open/close/high")
        return self


from typing import Union


class HistoryImportRequest(BaseModel):
    symbol: str = Field(default="XAUUSD")
    timeframe: Union[Literal["M1", "M5", "M15", "H1"]] = "M1"
    source: str = Field(default="mt5_windows", max_length=100)
    offset_seconds: int = 0
    candles: list[HistoryCandle] = Field(min_length=1, max_length=50000)


class OpenOrderRequest(BaseModel):
    side: Literal["buy", "sell"]
    lot: float = Field(gt=0)
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    note: str = "manual"


class CloseOrderRequest(BaseModel):
    note: str = "manual_close"


