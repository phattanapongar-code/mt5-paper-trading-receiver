from dataclasses import dataclass
from typing import Literal, Optional, Protocol


@dataclass
class Signal:
    action: Literal["open", "close", "hold"]
    side: Optional[Literal["buy", "sell"]] = None
    note: str = ""


class Strategy(Protocol):
    def on_tick(self, tick: dict, account: dict) -> Signal:
        ...
