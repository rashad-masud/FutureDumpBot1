from core.enums import SignalType
from signals.signal import Signal
from config.settings import (
    REQUIRE_VOLUME_CONFIRMATION,
    REQUIRE_EMA_ALIGNMENT,
    REQUIRE_ADX_CONFIRMATION,
    MIN_ADX,
    MIN_VOLUME_RATIO,
    MIN_TREND_AGE,
    ALLOW_LONG,
    ALLOW_SHORT,
)


class FuturesTrendStrategy:
    """Mechanical Donchian/Turtle-style trend-following entry model."""

    def evaluate(self, candles, analysis):
        if not analysis or not analysis.should_trade:
            return None
        if analysis.trend_age < MIN_TREND_AGE:
            return None
        if REQUIRE_ADX_CONFIRMATION and analysis.adx < MIN_ADX:
            return None
        if REQUIRE_VOLUME_CONFIRMATION and analysis.volume_ratio < MIN_VOLUME_RATIO:
            return None

        if analysis.gen_trend == "trend_up" and analysis.entry_breakout and ALLOW_LONG:
            if REQUIRE_EMA_ALIGNMENT and analysis.ema_fast <= analysis.ema_slow:
                return None
            return Signal(SignalType.LONG)

        if analysis.gen_trend == "trend_down" and analysis.entry_breakout and ALLOW_SHORT:
            if REQUIRE_EMA_ALIGNMENT and analysis.ema_fast >= analysis.ema_slow:
                return None
            return Signal(SignalType.SHORT)

        return None
