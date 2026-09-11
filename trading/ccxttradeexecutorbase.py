from abc import ABC, abstractmethod
import time
from typing import Optional

from core.position import Position
from trading.tradejournal import TradeJournal
from config.settings import (
    STARTING_CAPITAL, TAKER_FEE_PCT, RISK_PER_TRADE_PCT, MAX_MARGIN_PCT,
    MIN_STOP_PCT, MAX_STOP_PCT, STOP_ATR_MULTIPLIER, STOP_SWING_LOOKBACK,
    STOP_SWING_BUFFER_ATR, TRAIL_ACTIVATION_R, TRAIL_ATR_MULTIPLIER,
    TRAIL_MIN_DISTANCE_PCT, TRAIL_MAX_DISTANCE_PCT, STRONG_ADX, EXTREME_ADX,
    BASE_LEVERAGE, STRONG_TREND_LEVERAGE, EXTREME_TREND_LEVERAGE, MAX_LEVERAGE,
    EXIT_ON_OPPOSITE_BREAKOUT, EXIT_ON_EMA_REVERSAL, REVERSAL_CONFIRMATION_CANDLES,
    REINVEST_PROFITS,
)


class CCXTTradeExecutorBase(ABC):
    """Risk-controlled futures execution engine used by paper/live adapters."""

    def __init__(self):
        self.balance = STARTING_CAPITAL
        self.initial_capital = STARTING_CAPITAL
        self.position: Optional[Position] = None
        self.daily_pnl = 0.0
        self.journal = TradeJournal()
        self.trade_id_counter = 0
        self.reversal_count = 0

    def execute(self, symbol, signal, price, analysis, candles, *, candle_id=None, tick_id=None):
        if self.position or not signal:
            return
        self._open_position(symbol, signal.signal_type.value, price, analysis, candles, candle_id, tick_id)

    def _capital_base(self):
        return self.balance if REINVEST_PROFITS else self.initial_capital

    def _calculate_leverage(self, analysis):
        if analysis.adx >= EXTREME_ADX:
            return min(EXTREME_TREND_LEVERAGE, MAX_LEVERAGE)
        if analysis.adx >= STRONG_ADX:
            return min(STRONG_TREND_LEVERAGE, MAX_LEVERAGE)
        return min(BASE_LEVERAGE, MAX_LEVERAGE)

    def _calculate_stop(self, side, entry, analysis, candles):
        if analysis.atr <= 0:
            return None
        recent = candles[-min(len(candles), STOP_SWING_LOOKBACK):]
        if side == "long":
            swing = min(c["low"] for c in recent)
            stop = min(entry - analysis.atr * STOP_ATR_MULTIPLIER, swing - analysis.atr * STOP_SWING_BUFFER_ATR)
            distance = entry - stop
        else:
            swing = max(c["high"] for c in recent)
            stop = max(entry + analysis.atr * STOP_ATR_MULTIPLIER, swing + analysis.atr * STOP_SWING_BUFFER_ATR)
            distance = stop - entry
        pct = distance / entry
        if pct > MAX_STOP_PCT:
            return None
        if pct < MIN_STOP_PCT:
            distance = entry * MIN_STOP_PCT
            stop = entry - distance if side == "long" else entry + distance
        return stop

    def _open_position(self, symbol, side, price, analysis, candles, candle_id, tick_id):
        if side not in ("long", "short") or analysis.gen_trend not in ("trend_up", "trend_down"):
            return
        leverage = self._calculate_leverage(analysis)
        stop = self._calculate_stop(side, price, analysis, candles)
        if stop is None:
            print(f"[RISK] Skip {symbol}: stop distance outside configured envelope")
            return
        stop_distance = abs(price - stop)
        capital = self._capital_base()
        risk_amount = capital * RISK_PER_TRADE_PCT
        size = risk_amount / stop_distance
        notional = size * price
        max_notional = capital * MAX_MARGIN_PCT * leverage
        if notional > max_notional:
            notional = max_notional
            size = notional / price
        fee = notional * TAKER_FEE_PCT
        if fee >= capital:
            return
        self.balance -= fee
        self.trade_id_counter += 1
        self.position = Position(
            trade_id=self.trade_id_counter, symbol=symbol, side=side,
            entry_price=price, size=size, leverage=leverage,
            stop_loss=stop, initial_stop_distance=stop_distance,
            atr=analysis.atr, best_price=price,
            open_candle_id=candle_id, open_tick_id=tick_id,
        )
        self.journal.record_open(
            symbol=symbol, side=side, regime=analysis.gen_trend,
            entry_price=price, size=size, leverage=leverage,
            stop_pct=stop_distance / price, trade_id=self.position.trade_id,
            open_candle_id=candle_id, open_tick_id=tick_id,
        )
        print(f"[EXECUTOR] OPEN {side.upper()} trade={self.position.trade_id} {symbol} price={price:.6f} lev={leverage:.1f}x stop={stop:.6f} risk={risk_amount:.2f}")
        self._on_open(symbol, size, price, leverage, side)

    def manage_position(self, price, analysis=None, candles=None, *, tick_id=None, candle_id=None):
        if not self.position:
            return False
        pos = self.position
        if (pos.side == "long" and price <= pos.stop_loss) or (pos.side == "short" and price >= pos.stop_loss):
            self._close_position(price, "stop_loss", tick_id, candle_id)
            return True
        pnl = pos.pnl(price)
        r_multiple = pnl / (pos.initial_stop_distance * pos.size) if pos.initial_stop_distance else 0.0
        if r_multiple >= TRAIL_ACTIVATION_R:
            pos.trail_active = True
        pos.best_price = max(pos.best_price, price) if pos.side == "long" else min(pos.best_price, price)
        if pos.trail_active:
            distance = max(pos.atr * TRAIL_ATR_MULTIPLIER, pos.best_price * TRAIL_MIN_DISTANCE_PCT)
            distance = min(distance, pos.best_price * TRAIL_MAX_DISTANCE_PCT)
            candidate = pos.best_price - distance if pos.side == "long" else pos.best_price + distance
            if pos.side == "long":
                pos.trail_stop = max(pos.trail_stop or pos.stop_loss, candidate)
                if price <= pos.trail_stop:
                    self._close_position(price, "atr_trailing_stop", tick_id, candle_id)
                    return True
            else:
                pos.trail_stop = min(pos.trail_stop or pos.stop_loss, candidate)
                if price >= pos.trail_stop:
                    self._close_position(price, "atr_trailing_stop", tick_id, candle_id)
                    return True
        if analysis and candles:
            if EXIT_ON_OPPOSITE_BREAKOUT:
                if pos.side == "long" and price <= analysis.exit_level_long:
                    self._close_position(price, "donchian_exit", tick_id, candle_id)
                    return True
                if pos.side == "short" and price >= analysis.exit_level_short:
                    self._close_position(price, "donchian_exit", tick_id, candle_id)
                    return True
            if EXIT_ON_EMA_REVERSAL:
                opposite = (pos.side == "long" and analysis.gen_trend == "trend_down") or (pos.side == "short" and analysis.gen_trend == "trend_up")
                self.reversal_count = self.reversal_count + 1 if opposite else 0
                if self.reversal_count >= REVERSAL_CONFIRMATION_CANDLES:
                    self._close_position(price, "regime_reversal", tick_id, candle_id)
                    return True
        return False

    def _close_position(self, price, reason, tick_id=None, candle_id=None):
        pos = self.position
        pnl = pos.pnl(price)
        fee = abs(pos.size * price) * TAKER_FEE_PCT
        net = pnl - fee
        self.balance += net
        self.daily_pnl += net
        self.journal.record_close(
            trade_id=pos.trade_id, side=pos.side, entry_price=pos.entry_price,
            exit_price=price, pnl=net, balance_after=self.balance, reason=reason,
            open_candle_id=pos.open_candle_id, close_candle_id=candle_id,
            open_tick_id=pos.open_tick_id, close_tick_id=tick_id,
        )
        print(f"[EXECUTOR] CLOSE {pos.side.upper()} trade={pos.trade_id} price={price:.6f} pnl={net:.4f} ({pos.pnl_pct(price):.2f}%) reason={reason} balance={self.balance:.2f}")
        self._on_close(pos.size, price, pnl, pos.side)
        self.position = None
        self.reversal_count = 0

    @abstractmethod
    def _on_open(self, symbol, size, price, leverage, side):
        pass

    @abstractmethod
    def _on_close(self, size, price, pnl, side):
        pass
