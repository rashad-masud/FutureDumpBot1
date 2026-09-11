from config.settings import MIN_TREND_AGE_TO_TRADE
from core.enums import SignalType

class StrategyManager:
    def __init__(self, strategies):
        self.strategies = strategies
        self.min_trend_age = MIN_TREND_AGE_TO_TRADE

    def evaluate(self, symbol, candles, analysis):
        # Only trade if the regime is dump
        if analysis.gen_trend != "dump":
            return None

        # Optional trend age filter
        if analysis.trend_age < self.min_trend_age:
            print(f"[StrategyManager] trend_age={analysis.trend_age} < {self.min_trend_age}")
            return None

        for strategy in self.strategies:
            if "dump" not in strategy.supported_regimes:
                continue
            signal = strategy.evaluate(candles, analysis)
            if signal:
                return signal
        return None