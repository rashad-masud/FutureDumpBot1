from abc import ABC, abstractmethod
from datetime import datetime
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
    REINVEST_PROFITS, DONCHIAN_EXIT_MIN_R, REQUIRE_MTF_ALIGNMENT,
)


class CCXTTradeExecutorBase(ABC):
    """Risk-controlled futures execution engine used by paper/live adapters."""

    def __init__(self):
        self.balance = STARTING_CAPITAL
        self.initial_capital = STARTING_CAPITAL
        self.position: Optional[Position] = None
        self.daily_pnl = 0.0
        self.journal = TradeJournal()
        self.trade_id_counter = self._recover_next_trade_id()
        self.reversal_count = 0

    def _recover_next_trade_id(self):
        max_id = 0
        try:
            import csv
            with open(self.journal.file_path, "r", newline="") as f:
                for row in csv.DictReader(f):
                    try:
                        max_id = max(max_id, int(row.get("trade_id", 0) or 0))
                    except (TypeError, ValueError):
                        continue
        except OSError:
            pass
        return max_id

    def execute(self, symbol, signal, price, analysis, candles, *, candle_id=None, tick_id=None):
        if self.position or not signal:
            return
        self._open_position(symbol, signal.signal_type.value, price, analysis, candles, candle_id, tick_id)

    def _capital_base(self):
        return self.balance if REINVEST_PROFITS else self.initial_capital

    def _calculate_leverage(self, analysis):
        aligned = getattr(analysis, "mtf_aligned", False)
        if analysis.adx >= EXTREME_ADX and (not REQUIRE_MTF_ALIGNMENT or aligned):
            return min(EXTREME_TREND_LEVERAGE, MAX_LEVERAGE)
        if analysis.adx >= STRONG_ADX and (not REQUIRE_MTF_ALIGNMENT or aligned):
            return min(STRONG_TREND_LEVERAGE, MAX_LEVERAGE)
        return min(BASE_LEVERAGE, MAX_LEVERAGE)

    def _calculate_stop(self, side, entry, analysis, candles):
        if analysis.atr <= 0:
            return None
        recent = candles[-min(len(candles), STOP_SWING_LOOKBACK):]
        if side == "long":
            swing = min(c["low"] for c in recent)
            # Use the tighter of ATR and structure risk; never let the structure stop
            # silently become an oversized loss.
            stop = max(entry - analysis.atr * STOP_ATR_MULTIPLIER, swing - analysis.atr * STOP_SWING_BUFFER_ATR)
            distance = entry - stop
        else:
            swing = max(c["high"] for c in recent)
            stop = min(entry + analysis.atr * STOP_ATR_MULTIPLIER, swing + analysis.atr * STOP_SWING_BUFFER_ATR)
            distance = stop - entry
        if distance <= 0:
            return None
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
        if not analysis.should_trade or not analysis.entry_breakout:
            return
        if side == "short" and analysis.gen_trend != "trend_down":
            return
        if side == "long" and analysis.gen_trend != "trend_up":
            return
        if REQUIRE_MTF_ALIGNMENT and not getattr(analysis, "mtf_aligned", False):
            print(f"[RISK] Skip {symbol}: 15m/30m regime not aligned")
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
        entry_fee = notional * TAKER_FEE_PCT
        if entry_fee >= capital:
            return
        self.balance -= entry_fee
        self.trade_id_counter += 1
        self.position = Position(
            trade_id=self.trade_id_counter, symbol=symbol, side=side,
            entry_price=price, size=size, leverage=leverage,
            stop_loss=stop, initial_stop_distance=stop_distance,
            atr=analysis.atr, best_price=price, worst_price=price,
            open_candle_id=candle_id, open_tick_id=tick_id,
            entry_fee=entry_fee,
        )
        self.journal.record_open(
            symbol=symbol, side=side, regime=analysis.gen_trend,
            entry_price=price, size=size, leverage=leverage,
            stop_pct=stop_distance / price, trade_id=self.position.trade_id,
            open_candle_id=candle_id, open_tick_id=tick_id,
        )
        print(f"[EXECUTOR] OPEN {side.upper()} trade={self.position.trade_id} {symbol} price={price:.6f} lev={leverage:.1f}x stop={stop:.6f} risk={risk_amount:.2f} fee={entry_fee:.4f}")
        self._on_open(symbol, size, price, leverage, side)

    def manage_position(self, price, analysis=None, candles=None, *, tick_id=None, candle_id=None):
        if not self.position:
            return False
        pos = self.position

        # Track excursion before evaluating exits so the journal captures what
        # the trade actually experienced, not just its final result.
        pos.best_price = max(pos.best_price, price) if pos.side == "long" else min(pos.best_price, price)
        pos.worst_price = min(pos.worst_price, price) if pos.side == "long" else max(pos.worst_price, price)

        if (pos.side == "long" and price <= pos.stop_loss) or (pos.side == "short" and price >= pos.stop_loss):
            self._close_position(price, "stop_loss", tick_id, candle_id)
            return True

        pnl = pos.pnl(price)
        risk_value = pos.initial_stop_distance * pos.size
        r_multiple = pnl / risk_value if risk_value else 0.0
        if r_multiple >= TRAIL_ACTIVATION_R:
            pos.trail_active = True

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
            # Donchian is allowed to take a trade out only when it is at least
            # non-negative in R. Losing trades are governed by the hard stop or
            # confirmed regime reversal instead of waiting for a distant channel.
            if EXIT_ON_OPPOSITE_BREAKOUT and r_multiple >= DONCHIAN_EXIT_MIN_R:
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
        if pos is None:
            return
        gross_pnl = pos.pnl(price)
        exit_notional = abs(pos.size * price)
        exit_fee = exit_notional * TAKER_FEE_PCT
        net_trade_pnl = gross_pnl - pos.entry_fee - exit_fee
        self.balance += gross_pnl - exit_fee
        self.daily_pnl += net_trade_pnl
        self.journal.record_close(
            trade_id=pos.trade_id, side=pos.side, entry_price=pos.entry_price,
            exit_price=price, pnl=net_trade_pnl, balance_after=self.balance, reason=reason,
            open_candle_id=pos.open_candle_id, close_candle_id=candle_id,
            open_tick_id=pos.open_tick_id, close_tick_id=tick_id,
            entry_fee=pos.entry_fee, exit_fee=exit_fee,
            gross_pnl=gross_pnl, initial_stop=pos.stop_loss,
            best_price=pos.best_price, worst_price=pos.worst_price,
            leverage=pos.leverage,
            duration_seconds=max(0.0, datetime.utcnow().timestamp() - pos.opened_at),
        )
        print(f"[EXECUTOR] CLOSE {pos.side.upper()} trade={pos.trade_id} price={price:.6f} gross={gross_pnl:.4f} fees={pos.entry_fee + exit_fee:.4f} net={net_trade_pnl:.4f} ({pos.pnl_pct(price):.2f}%) reason={reason} balance={self.balance:.2f}")
        self._on_close(pos.size, price, gross_pnl, pos.side)
        self.position = None
        self.reversal_count = 0

    @abstractmethod
    def _on_open(self, symbol, size, price, leverage, side):
        pass

    @abstractmethod
    def _on_close(self, size, price, pnl, side):
        pass
