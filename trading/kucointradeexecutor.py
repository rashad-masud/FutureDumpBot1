from trading.ccxttradeexecutorbase import CCXTTradeExecutorBase

class KucoinTradeExecutor(CCXTTradeExecutorBase):
    def __init__(self, exchange):
        super().__init__()
        self.exchange = exchange

    def _on_open(self, symbol, side, size, price, leverage):
        self.exchange.create_market_order(
            symbol=symbol,
            side="buy" if side == "long" else "sell",
            amount=size,
            params={"leverage": leverage}
        )

    def _on_close(self, side, size, price, pnl):
        self.exchange.create_market_order(
            symbol=symbol,
            side="sell" if side == "long" else "buy",
            amount=size
        )
