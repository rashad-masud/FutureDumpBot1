from enum import Enum

class SignalType(Enum):
    SHORT = "short"
    # LONG removed – we only short

class MarketRegime(Enum):
    DUMP = "dump"
    TREND_DOWN = "trend_down"
    RANGE = "range"
    VOLATILE = "volatile"
    BREAKOUT = "breakout"
    # TREND_UP removed