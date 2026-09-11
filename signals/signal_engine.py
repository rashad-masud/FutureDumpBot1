from collections import deque
import statistics
from typing import Optional, List, Dict

from config.settings import (
    REGIME_LOOKBACK_CANDLES,
    FAST_VOL_LOOKBACK,
    MICRO_LOOKBACK,
    MICRO_CONFIRMATION,
    BREAKOUT_VOL_MULTIPLIER,
    BREAKOUT_PRICE_CHANGE_PCT,
    MIN_TREND_PCT,
    STRONG_TREND_THRESHOLD,
    EXTREME_VOLATILITY_THRESHOLD,
    MAX_VOLATILITY_TO_AVOID,
    MAX_CONFIDENCE,
    DUMP_LOOKBACK_CANDLES,
    DUMP_CUMULATIVE_PCT,
    DUMP_SINGLE_CANDLE_PCT,
)

from core.enums import MarketRegime
from core.model import MarketAnalysis


class SignalEngine:
    def __init__(self, window_size: int):
        self.window_size = window_size
        self.candles: Dict[str, deque] = {}
        self.market_analysis: Dict[str, MarketAnalysis] = {}
        self._last_regime: Dict[str, str] = {}
        self._trend_age: Dict[str, int] = {}

    def update(self, symbol: str, candle: dict) -> None:
        if symbol not in self.candles:
            self.candles[symbol] = deque(maxlen=self.window_size)
        self.candles[symbol].append(candle)
        if len(self.candles[symbol]) >= REGIME_LOOKBACK_CANDLES:
            self._analyze(symbol)

    def get_market_analysis(self, symbol: str) -> Optional[MarketAnalysis]:
        return self.market_analysis.get(symbol)

    def _detect_dump(self, candles: List[dict]) -> bool:
        recent = candles[-DUMP_LOOKBACK_CANDLES:]
        if len(recent) < 2:
            return False
        closes = [c["close"] for c in recent]
        cumulative = (closes[-1] - closes[0]) / closes[0]
        single = (closes[-1] - closes[-2]) / closes[-2]
        return (cumulative <= -DUMP_CUMULATIVE_PCT
                or single <= -DUMP_SINGLE_CANDLE_PCT)

    def _analyze(self, symbol: str) -> None:
        candles = list(self.candles[symbol])
        window = candles[-REGIME_LOOKBACK_CANDLES:]
        if len(window) < 2:
            return

        closes = [c["close"] for c in window]
        trend_pct = (closes[-1] - closes[0]) / closes[0]

        returns = [
            abs((closes[i] - closes[i-1]) / closes[i-1])
            for i in range(1, len(closes))
        ]
        volatility_pct = statistics.mean(returns)
        trend_strength = abs(trend_pct) / max(volatility_pct, 1e-6)

        fast_returns = [
            abs((window[-i]["close"] - window[-i-1]["close"]) / window[-i-1]["close"])
            for i in range(1, FAST_VOL_LOOKBACK + 1)
        ]
        fast_vol = statistics.mean(fast_returns)

        recent = candles[-MICRO_LOOKBACK:]
        ups = sum(1 for c in recent if c["close"] > c["open"])
        downs = sum(1 for c in recent if c["close"] < c["open"])
        if ups >= MICRO_CONFIRMATION:
            candle_trend = "up"
        elif downs >= MICRO_CONFIRMATION:
            candle_trend = "down"
        else:
            candle_trend = "flat"

        if self._detect_dump(candles):
            regime = MarketRegime.DUMP
        elif volatility_pct > MAX_VOLATILITY_TO_AVOID:
            regime = MarketRegime.VOLATILE
        elif (fast_vol > volatility_pct * BREAKOUT_VOL_MULTIPLIER
              and abs(trend_pct) > BREAKOUT_PRICE_CHANGE_PCT):
            regime = MarketRegime.BREAKOUT
        elif abs(trend_pct) > MIN_TREND_PCT and trend_strength >= STRONG_TREND_THRESHOLD:
            if trend_pct < 0:
                regime = MarketRegime.TREND_DOWN
            else:
                regime = MarketRegime.RANGE
        else:
            regime = MarketRegime.RANGE

        regime_value = regime.value
        prev = self._last_regime.get(symbol)
        if prev == regime_value:
            self._trend_age[symbol] = self._trend_age.get(symbol, 0) + 1
        else:
            self._trend_age[symbol] = 1
        self._last_regime[symbol] = regime_value

        self.market_analysis[symbol] = MarketAnalysis(
            gen_trend=regime_value,
            candle_trend=candle_trend,
            trend_strength=trend_strength,
            volatility_pct=volatility_pct,
            price_change_pct=trend_pct,
            price_range_pct=0.0,
            is_high_volatility=volatility_pct > EXTREME_VOLATILITY_THRESHOLD,
            should_trade=regime_value not in ("volatile",),
            trade_reason=regime_value,
            confidence=min(trend_strength / STRONG_TREND_THRESHOLD, MAX_CONFIDENCE),
            trend_age=self._trend_age[symbol],
        )
        print(f"[LIVE] {symbol} | {regime_value} | trend={trend_pct:.4f} | vol={volatility_pct:.4f} | age={self._trend_age[symbol]} | candle={candle_trend}")