from app.paper_engine import PaperTradingEngine


class MemoryStorage:
    def __init__(self):
        self.trades = []

    def insert_trade(self, trade):
        self.trades.append(trade)


def tick(bid, ask):
    return {"type": "tick", "symbol": "XAUUSD", "bid": bid, "ask": ask, "timestamp": 1, "seq": 1}


def test_buy_uses_ask_to_enter_and_bid_to_exit():
    storage = MemoryStorage()
    engine = PaperTradingEngine(10000, contract_size=100, default_lot=0.01, storage=storage)
    engine.on_tick(tick(3000.0, 3000.5))
    engine.open_position_manual("buy", 0.01, None, None, "test")
    engine.on_tick(tick(3001.0, 3001.5))
    trade = engine.close_position_manual("test_close")
    assert trade["entry_price"] == 3000.5
    assert trade["exit_price"] == 3001.0
    assert trade["pnl"] == 0.5


def test_sell_uses_bid_to_enter_and_ask_to_exit():
    storage = MemoryStorage()
    engine = PaperTradingEngine(10000, contract_size=100, default_lot=0.01, storage=storage)
    engine.on_tick(tick(3000.0, 3000.5))
    engine.open_position_manual("sell", 0.01, None, None, "test")
    engine.on_tick(tick(2999.0, 2999.5))
    trade = engine.close_position_manual("test_close")
    assert trade["entry_price"] == 3000.0
    assert trade["exit_price"] == 2999.5
    assert trade["pnl"] == 0.5
