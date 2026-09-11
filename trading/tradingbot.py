import time
from core.enums import SignalType

class TradingBot:
    def __init__(self, signal_engine, strategy_manager, executor, on_trade_closed=None):
        self.signal_engine = signal_engine
        self.strategy_manager = strategy_manager
        self.executor = executor
        self.on_trade_closed = on_trade_closed
        self._tick_count = 0
        self.tick_id = 0
        self.current_candle_id = None

    def on_price_tick(self, symbol, price):
        self._tick_count += 1
        self.tick_id += 1
        if self.executor.position:
            self.executor.manage_position(price, tick_id=self.tick_id, candle_id=self.current_candle_id)

    def on_candle(self, symbol, candle):
        self.current_candle_id = candle["timestamp"]
        self.signal_engine.update(symbol, candle)

        analysis = self.signal_engine.get_market_analysis(symbol)
        if not analysis:
            return

        candles = list(self.signal_engine.candles[symbol])

        # Candle return for context
        candle_return = None
        if len(candles) >= 2:
            prev_close = candles[-2]["close"]
            candle_return = (candle["close"] - prev_close) / prev_close
            self.executor.update_candle_context(candle_return=candle_return, volatility=analysis.volatility_pct)

        # Manage open position first
        if self.executor.position:
            closed = self.executor.manage_position(
                price=candle["close"],
                candle_return=candle_return,
                tick_id=self.tick_id,
                candle_id=self.current_candle_id
            )
            if closed:
                if self.on_trade_closed:
                    self.on_trade_closed()
                return

        # Evaluate entry signal
        signal = self.strategy_manager.evaluate(symbol, candles, analysis)
        if not signal:
            return

        # Only short signals
        if signal != SignalType.SHORT:
            return

        # Entry price: slightly above close to avoid exact low
        entry_price = candle["close"] * 1.001

        self.executor.execute(
            symbol,
            signal,
            entry_price,
            analysis.gen_trend,
            analysis.volatility_pct,
            size_factor=1.0,
            candleid=self.current_candle_id,
            tickid=self.tick_id
        )