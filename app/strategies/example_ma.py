from collections import deque
from statistics import mean

from .base import Signal


class ExampleMovingAverageStrategy:
    """A simple smoke-test strategy, not an investment recommendation.

    It opens when fast MA crosses slow MA and closes/reverses when the
    direction changes. Keep disabled unless you explicitly want demo orders.
    """

    def __init__(self, fast_period: int = 5, slow_period: int = 20):
        if fast_period >= slow_period:
            raise ValueError("fast_period must be smaller than slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.prices = deque(maxlen=slow_period)
        self.last_direction: str | None = None

    def on_tick(self, tick: dict, account: dict) -> Signal:
        self.prices.append(float(tick["bid"]))
        if len(self.prices) < self.slow_period:
            return Signal(action="hold", note="warming_up")

        prices = list(self.prices)
        fast = mean(prices[-self.fast_period:])
        slow = mean(prices)
        direction = "buy" if fast > slow else "sell" if fast < slow else None

        if direction is None or direction == self.last_direction:
            return Signal(action="hold", note="no_cross")

        self.last_direction = direction
        position = account.get("open_position")
        if position and position["side"] != direction:
            return Signal(action="close", note=f"ma_cross_close_for_{direction}")
        if not position:
            return Signal(action="open", side=direction, note=f"ma_cross_{direction}")
        return Signal(action="hold", note="same_side")
