from trading.ccxttradeexecutorbase import CCXTTradeExecutorBase

class CCXTPaperTradeExecutor(CCXTTradeExecutorBase):
    def _on_open(self, symbol, size, price, leverage):
        print(f"[PAPER OPEN] SHORT {symbol} size={size:.6f} lev={leverage}x @ {price:.2f}")

    def _on_close(self, size, price, pnl):
        print(f"[PAPER CLOSE] SHORT pnl={pnl:.2f} balance={self.balance:.2f}")