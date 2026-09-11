from trading.ccxttradeexecutorbase import CCXTTradeExecutorBase


class CCXTPaperTradeExecutor(CCXTTradeExecutorBase):
    def _on_open(self, symbol, size, price, leverage, side):
        print(f"[PAPER OPEN] {side.upper()} {symbol} size={size:.6f} lev={leverage:.1f}x @ {price:.6f}")

    def _on_close(self, size, price, pnl, side):
        print(f"[PAPER CLOSE] {side.upper()} pnl={pnl:.4f} balance={self.balance:.2f}")
