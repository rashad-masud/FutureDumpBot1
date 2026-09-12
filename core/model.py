from dataclasses import dataclass
import time


@dataclass
class MarketAnalysis:
    gen_trend: str
    candle_trend: str
    trend_strength: float
    volatility_pct: float
    price_change_pct: float
    price_range_pct: float
    is_high_volatility: bool
    should_trade: bool
    trade_reason: str
    confidence: float
    trend_age: int = 0
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    atr: float = 0.0
    atr_pct: float = 0.0
    adx: float = 0.0
    volume_ratio: float = 0.0
    entry_breakout: bool = False
    exit_level_long: float = 0.0
    exit_level_short: float = 0.0
    trend_15m: str = "unknown"
    trend_30m: str = "unknown"
    trend_60m: str = "unknown"
    adx_15m: float = 0.0
    adx_30m: float = 0.0
    adx_60m: float = 0.0
    mtf_aligned: bool = False
    higher_tf_not_bearish: bool = True
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()
