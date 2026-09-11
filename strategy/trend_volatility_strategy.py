from core.enums import SignalType
from signals.signal import Signal   # ✅ CORRECT
from strategy.base_strategy import BaseStrategy
from config.settings import (
    FIVE_CANDLE_LOOKBACK,
    MIN_5C_MOVE_PCT,
    VOL_5C_MULTIPLIER,
)


class TrendVolatilityStrategy(BaseStrategy):
    supported_regimes = {"trend_up", "trend_down"}
    min_trend_age = 2

    def __init__(self):
        super().__init__(name="TrendVolatilityStrategy", version="2.0")

    # --------------------------------------------------
    # ENGINE ENTRY POINT (NEW)
    # --------------------------------------------------
    def generate(self, ctx):
        candles = ctx.get("candles")
        analysis = ctx.get("analysis")

        if not candles or not analysis:
            return None

        if analysis.gen_trend not in self.supported_regimes:
            return None

        if analysis.trend_age < self.min_trend_age:
            return None

        activity = self._directional_activity(candles, analysis)
        if activity == "weak":
            return None

        size_factor = 1.0 if activity == "strong" else 0.5

        if analysis.gen_trend == "trend_up":
            return Signal(SignalType.LONG, size_factor)

        if analysis.gen_trend == "trend_down":
            return Signal(SignalType.SHORT, size_factor)

        return None

    # --------------------------------------------------
    # BACKWARD COMPATIBILITY (OLD ENGINE)
    # --------------------------------------------------
    def evaluate(self, candles, analysis):
        return self.generate({
            "candles": candles,
            "analysis": analysis
        })

    # --------------------------------------------------
    # ACTIVITY FILTER
    # --------------------------------------------------
    def _directional_activity(self, candles, analysis):
        if len(candles) < FIVE_CANDLE_LOOKBACK:
            return "weak"

        last_5 = candles[-FIVE_CANDLE_LOOKBACK:]
        open_5 = last_5[0]["open"]
        close_1 = last_5[-1]["close"]

        move = (close_1 - open_5) / open_5

        if analysis.gen_trend == "trend_up" and move <= 0:
            return "weak"

        if analysis.gen_trend == "trend_down" and move >= 0:
            return "weak"

        strength = abs(move)
        min_req = max(
            MIN_5C_MOVE_PCT,
            analysis.volatility_pct * VOL_5C_MULTIPLIER
        )

        if strength < min_req * 0.6:
            return "weak"
        if strength < min_req:
            return "medium"

        return "strong"
