from core.enums import SignalType
import time

class PaperExchange:
    def __init__(self, starting_balance: float = 1000):
        self.balance = starting_balance
        self.position = None        # "LONG", "SHORT", None
        self.entry_price = None
        self.trades = []

    def place_market_order(self, symbol, signal: SignalType, price: float, quantity: float):
        trade = {
            "symbol": symbol,
            "side": signal.value,
            "price": price,
            "qty": quantity,
            "timestamp": time.time(),
        }

        self.trades.append(trade)
        return trade
