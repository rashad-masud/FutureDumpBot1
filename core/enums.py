from enum import Enum


class SignalType(Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class MarketRegime(Enum):
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE = "range"
    VOLATILE = "volatile"
    EXTREME = "extreme"
