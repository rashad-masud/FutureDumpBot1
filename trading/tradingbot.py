class TradingBot:
    def __init__(self, signal_engine, strategy_manager, executor, on_trade_closed=None):
        self.signal_engine = signal_engine
        self.strategy_manager = strategy_manager
        self.executor = executor
        self.on_trade_closed = on_trade_closed
        self.tick_id = 0
        self.current_candle_id = None
        self.ready = False

    def set_ready(self):
        self.ready = True

    def on_price_tick(self, symbol, price):
        self.tick_id += 1
        if not self.ready or not self.executor.position:
            return
        analysis = self.signal_engine.get_market_analysis(symbol)
        candles = list(self.signal_engine.candles.get(symbol, []))
        closed = self.executor.manage_position(price=price, analysis=analysis, candles=candles, tick_id=self.tick_id, candle_id=self.current_candle_id)
        if closed and self.on_trade_closed:
            self.on_trade_closed()

    def on_candle(self, symbol, candle):
        self.current_candle_id = candle["timestamp"]
        self.signal_engine.update(symbol, candle)
        if not self.ready:
            return

        analysis = self.signal_engine.get_market_analysis(symbol)
        if not analysis:
            return
        candles = list(self.signal_engine.candles[symbol])

        if self.executor.position:
            closed = self.executor.manage_position(price=candle["close"], analysis=analysis, candles=candles, tick_id=self.tick_id, candle_id=self.current_candle_id)
            if closed:
                if self.on_trade_closed:
                    self.on_trade_closed()
                return

        signal = self.strategy_manager.evaluate(symbol, candles, analysis)
        if signal:
            self.executor.execute(symbol, signal, candle["close"], analysis, candles, candle_id=self.current_candle_id, tick_id=self.tick_id)
