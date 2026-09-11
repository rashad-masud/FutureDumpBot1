from enum import Enum

class SignalType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"
    IGNORE = "IGNORE"   # optional, but useful

class MarketRegime(Enum):
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE = "range"
    BREAKOUT = "breakout"
    VOLATILE = "volatile"

class OrderType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    
    
    @property
    def value(self):
        return self._value_

class MarketTrend(Enum):
    STRONG_UP = "STRONG_UP"
    UP = "UP"
    NEUTRAL = "NEUTRAL"
    DOWN = "DOWN"
    STRONG_DOWN = "STRONG_DOWN"
    
    @property
    def value(self):
        return self._value_

class TimeFrame(Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"
    
    @property
    def value(self):
        return self._value_

class ExitReason(Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"
    TIME_EXIT = "TIME_EXIT"
    TREND_REVERSAL = "TREND_REVERSAL"
    MANUAL = "MANUAL"
    EMERGENCY = "EMERGENCY"
    SHUTDOWN = "SHUTDOWN"
    DATA_ERROR = "DATA_ERROR"
    
    @property
    def value(self):
        return self._value_
