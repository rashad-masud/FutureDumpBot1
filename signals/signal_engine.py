from collections import deque
from typing import Dict, Optional, List

from config.settings import (
    WINDOW_SIZE,
    DONCHIAN_ENTRY_PERIOD,
    DONCHIAN_EXIT_PERIOD,
    EMA_FAST_PERIOD,
    EMA_SLOW_PERIOD,
    ATR_PERIOD,
    ADX_PERIOD,
    MIN_ADX,
    MIN_TREND_PCT,
    MAX_ATR_PCT,
    MIN_ATR_PCT,
    MIN_VOLUME_RATIO,
    BREAKOUT_BUFFER_ATR,
)
from core.enums import MarketRegime
from core.model import MarketAnalysis


class SignalEngine:
    """Closed-bar market regime and indicator engine.

    The model is deliberately mechanical: higher-timeframe-style trend context
    is represented by EMA alignment and ADX, while Donchian channels provide
    objective breakout/exit levels and ATR supplies volatility/risk distance.
    """

    def __init__(self, window_size: int = WINDOW_SIZE):
        self.window_size = window_size
        self.candles: Dict[str, deque] = {}
        self.market_analysis: Dict[str, MarketAnalysis] = {}
        self._last_regime: Dict[str, str] = {}
        self._trend_age: Dict[str, int] = {}

    def update(self, symbol: str, candle: dict) -> None:
        if symbol not in self.candles:
            self.candles[symbol] = deque(maxlen=self.window_size)
        self.candles[symbol].append(candle)
        self._analyze(symbol)

    def get_market_analysis(self, symbol: str) -> Optional[MarketAnalysis]:
        return self.market_analysis.get(symbol)

    @staticmethod
    def _ema(values: List[float], period: int) -> float:
        if not values:
            return 0.0
        alpha = 2.0 / (period + 1.0)
        ema = values[0]
        for value in values[1:]:
            ema = alpha * value + (1.0 - alpha) * ema
        return ema

    @staticmethod
    def _atr(candles: List[dict], period: int) -> float:
        if len(candles) < 2:
            return 0.0
        trs = []
        for i in range(1, len(candles)):
            current = candles[i]
            previous_close = candles[i - 1]["close"]
            trs.append(max(
                current["high"] - current["low"],
                abs(current["high"] - previous_close),
                abs(current["low"] - previous_close),
            ))
        sample = trs[-period:]
        return sum(sample) / len(sample) if sample else 0.0

    @staticmethod
    def _adx(candles: List[dict], period: int) -> float:
        if len(candles) < period + 1:
            return 0.0
        plus_dm = []
        minus_dm = []
        trs = []
        for i in range(1, len(candles)):
            cur = candles[i]
            prev = candles[i - 1]
            up = cur["high"] - prev["high"]
            down = prev["low"] - cur["low"]
            plus_dm.append(up if up > down and up > 0 else 0.0)
            minus_dm.append(down if down > up and down > 0 else 0.0)
            trs.append(max(
                cur["high"] - cur["low"],
                abs(cur["high"] - prev["close"]),
                abs(cur["low"] - prev["close"]),
            ))
        plus_dm = plus_dm[-period:]
        minus_dm = minus_dm[-period:]
        trs = trs[-period:]
        tr_sum = sum(trs)
        if tr_sum <= 0:
            return 0.0
        plus_di = 100.0 * sum(plus_dm) / tr_sum
        minus_di = 100.0 * sum(minus_dm) / tr_sum
        denom = plus_di + minus_di
        return 100.0 * abs(plus_di - minus_di) / denom if denom else 0.0

    def _analyze(self, symbol: str) -> None:
        candles = list(self.candles[symbol])
        minimum = max(
            EMA_SLOW_PERIOD,
            DONCHIAN_ENTRY_PERIOD + 1,
            DONCHIAN_EXIT_PERIOD + 1,
            ATR_PERIOD + 1,
            ADX_PERIOD + 1,
        )
        if len(candles) < minimum:
            return

        closes = [c["close"] for c in candles]
        ema_fast = self._ema(closes[-EMA_SLOW_PERIOD:], EMA_FAST_PERIOD)
        ema_slow = self._ema(closes[-EMA_SLOW_PERIOD:], EMA_SLOW_PERIOD)
        atr = self._atr(candles, ATR_PERIOD)
        close = closes[-1]
        atr_pct = atr / close if close else 0.0
        adx = self._adx(candles, ADX_PERIOD)

        trend_window = closes[-EMA_SLOW_PERIOD:]
        price_change_pct = ((trend_window[-1] - trend_window[0]) / trend_window[0]) if trend_window[0] else 0.0
        volume_sample = [c["volume"] for c in candles[-DONCHIAN_ENTRY_PERIOD:]]
        avg_volume = sum(volume_sample[:-1]) / max(len(volume_sample) - 1, 1)
        volume_ratio = volume_sample[-1] / avg_volume if avg_volume else 0.0

        prior_entry = candles[-DONCHIAN_ENTRY_PERIOD - 1:-1]
        prior_exit = candles[-DONCHIAN_EXIT_PERIOD - 1:-1]
        highest_entry = max(c["high"] for c in prior_entry)
        lowest_entry = min(c["low"] for c in prior_entry)
        highest_exit = max(c["high"] for c in prior_exit)
        lowest_exit = min(c["low"] for c in prior_exit)

        healthy_volatility = MIN_ATR_PCT <= atr_pct <= MAX_ATR_PCT
        up_alignment = ema_fast > ema_slow and close > ema_fast
        down_alignment = ema_fast < ema_slow and close < ema_fast
        trend_exists = abs(price_change_pct) >= MIN_TREND_PCT and adx >= MIN_ADX

        if not healthy_volatility:
            regime = MarketRegime.VOLATILE
        elif trend_exists and up_alignment:
            regime = MarketRegime.TREND_UP
        elif trend_exists and down_alignment:
            regime = MarketRegime.TREND_DOWN
        else:
            regime = MarketRegime.RANGE

        regime_value = regime.value
        if self._last_regime.get(symbol) == regime_value:
            age = self._trend_age.get(symbol, 0) + 1
        else:
            age = 1
        self._last_regime[symbol] = regime_value
        self._trend_age[symbol] = age

        buffer = atr * BREAKOUT_BUFFER_ATR
        breakout_up = close > highest_entry + buffer
        breakout_down = close < lowest_entry - buffer
        entry_breakout = (regime == MarketRegime.TREND_UP and breakout_up) or (regime == MarketRegime.TREND_DOWN and breakout_down)
        volume_ok = volume_ratio >= MIN_VOLUME_RATIO
        confidence = min(1.0, adx / 100.0)

        self.market_analysis[symbol] = MarketAnalysis(
            gen_trend=regime_value,
            candle_trend="up" if closes[-1] > candles[-1]["open"] else "down" if closes[-1] < candles[-1]["open"] else "flat",
            trend_strength=adx,
            volatility_pct=atr_pct,
            price_change_pct=price_change_pct,
            price_range_pct=(highest_entry - lowest_entry) / close if close else 0.0,
            is_high_volatility=atr_pct > MAX_ATR_PCT,
            should_trade=(regime in (MarketRegime.TREND_UP, MarketRegime.TREND_DOWN) and age >= 1 and volume_ok),
            trade_reason="healthy_trend_breakout" if entry_breakout and volume_ok else regime_value,
            confidence=confidence,
            trend_age=age,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            atr=atr,
            atr_pct=atr_pct,
            adx=adx,
            volume_ratio=volume_ratio,
            entry_breakout=entry_breakout,
            exit_level_long=lowest_exit,
            exit_level_short=highest_exit,
        )

        print(
            f"[REGIME] {symbol} | {regime_value} | ADX={adx:.1f} | "
            f"ATR%={atr_pct:.3%} | EMA={ema_fast:.4f}/{ema_slow:.4f} | "
            f"volx={volume_ratio:.2f} | breakout={entry_breakout}"
        )
