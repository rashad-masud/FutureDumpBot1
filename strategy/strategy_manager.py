class StrategyManager:
    def __init__(self, strategies):
        self.strategies = strategies

    def evaluate(self, symbol, candles, analysis):
        if not analysis or not analysis.should_trade:
            return None
        for strategy in self.strategies:
            signal = strategy.evaluate(candles, analysis)
            if signal:
                return signal
        return None
