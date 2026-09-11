from abc import ABC, abstractmethod
from collections import deque
import time
from typing import Optional
from core.position import Position
from trading.tradejournal import TradeJournal
from config.settings import (
    STARTING_CAPITAL,
    TAKER_FEE_PCT,
    RISK_PER_TRADE_PCT,
    REGIME_SIZE_MULTIPLIER,
    LEVERAGE_INITIAL,
    LEVERAGE_STEP,
    LEVERAGE_MAX,
    LEVERAGE_RESET_ON_LOSS,
    VOL_STOP_MULTIPLIER,
    MIN_STOP_PCT,
    MAX_STOP_PCT,
    MAX_TOTAL_EXPOSURE_PCT,
    TRAIL_TRIGGER_PNL,
    TRAIL_DISTANCE_PCT,
    REINVEST_PROFITS,
    MIN_PROFIT_PCT_TO_CONTINUE,
)

class CCXTTradeExecutorBase(ABC):
    def __init__(self):
        self.balance = STARTING_CAPITAL
        self.initial_capital = STARTING_CAPITAL
        self.position: Optional[Position] = None
        self.daily_pnl = 0.0
        self.journal = TradeJournal()
        self.against_candle_count = 0
        self.recent_returns = deque(maxlen=10)
        self.volatility_history = deque(maxlen=20)
        self.trade_id_counter = 0
        self.consecutive_wins = 0

    # ==========================================================
    # ENTRY
    # ==========================================================
    def execute(self, symbol, signal, price, regime, volatility_pct, size_factor=1.0, candleid=None, tickid=None):
        if self.position:
            return
        if signal.value != "short":
            return
        self._open_position(
            symbol=symbol,
            price=price,
            regime=regime,
            volatility_pct=volatility_pct,
            size_factor=size_factor,
            candle_id=candleid,
            tick_id=tickid
        )

    def _get_capital_base(self):
        """Return the capital to use for position sizing based on REINVEST_PROFITS setting."""
        return self.balance if REINVEST_PROFITS else self.initial_capital

    def _open_position(
        self,
        symbol,
        price,
        regime,
        volatility_pct,
        size_factor,
        *,
        candle_id=None,
        tick_id=None,
    ):
        stop_pct = self._calculate_stop_pct(volatility_pct)
        leverage = self._calculate_leverage(regime)

        stop_distance = price * stop_pct
        if stop_distance <= 0:
            return

        capital_base = self._get_capital_base()
        risk_amount = capital_base * RISK_PER_TRADE_PCT
        risk_amount *= size_factor
        risk_amount *= REGIME_SIZE_MULTIPLIER.get(regime, 1.0)

        size = (risk_amount * leverage) / stop_distance
        notional = size * price
        max_notional = capital_base * MAX_TOTAL_EXPOSURE_PCT
        if notional > max_notional:
            notional = max_notional
            size = notional / price

        fee = notional * TAKER_FEE_PCT
        required_margin = notional / leverage
        if required_margin + fee > capital_base:
            return

        self.balance -= fee
        self.trade_id_counter += 1

        self.position = Position(
            trade_id=self.trade_id_counter,
            symbol=symbol,
            entry_price=price,
            size=size,
            leverage=leverage,
            stop_pct=stop_pct,
            opened_at=time.time(),
            open_candle_id=candle_id,
            open_tick_id=tick_id,
            best_price=price,
            trail_active=False,
        )
        print(f"[EXECUTOR] OPEN trade={self.position.trade_id} SHORT {symbol} price={price:.2f} lev={leverage}x")
        self._on_open(symbol, size, price, leverage)

    # ==========================================================
    # EXIT MANAGEMENT
    # ==========================================================
    def manage_position(self, price, candle_return=None, *, tick_id=None, candle_id=None):
        if not self.position:
            return False

        if self._check_stop(price):
            return True

        if self._check_trailing_stop(price):
            return True

        return False

    def _check_stop(self, price):
        stop_price = self.position.entry_price * (1 + self.position.stop_pct)
        if price >= stop_price:
            self._close_position(price, reason="stop")
            return True
        return False

    def _check_trailing_stop(self, price):
        pos = self.position
        pnl_pct = (pos.entry_price - price) / pos.entry_price

        if not pos.trail_active:
            if pnl_pct < TRAIL_TRIGGER_PNL:
                return False
            pos.trail_active = True
            pos.best_price = price
            return False

        if price < pos.best_price:
            pos.best_price = price

        trail_pct = max(pos.stop_pct * 0.7, TRAIL_DISTANCE_PCT)
        trail_price = pos.best_price * (1 + trail_pct)
        if price >= trail_price:
            self._close_position(price, reason="trailing_stop")
            return True
        return False

    def _close_position(self, price, reason, *, tick_id=None, candle_id=None):
        pos = self.position
        pnl = (pos.entry_price - price) * pos.size
        pnl_pct = (pos.entry_price - price) / pos.entry_price * 100  # profit percentage
        fee = abs(pos.size * price) * TAKER_FEE_PCT
        self.balance += pnl - fee
        self.daily_pnl += pnl

        # Update consecutive wins based on profit threshold
        if pnl > 0:
            if pnl_pct >= MIN_PROFIT_PCT_TO_CONTINUE:
                self.consecutive_wins += 1
            else:
                # Profit too small – reset progression
                if LEVERAGE_RESET_ON_LOSS:
                    self.consecutive_wins = 0
        else:
            if LEVERAGE_RESET_ON_LOSS:
                self.consecutive_wins = 0

        self.journal.record_close(
            trade_id=pos.trade_id,
            side="short",
            entry_price=pos.entry_price,
            exit_price=price,
            pnl=pnl - fee,
            balance_after=self.balance,
            reason=reason,
            open_candle_id=pos.open_candle_id,
            close_candle_id=candle_id,
            open_tick_id=pos.open_tick_id,
            close_tick_id=tick_id,
        )
        self._on_close(pos.size, price, pnl)
        print(f"[EXECUTOR] CLOSE trade={pos.trade_id} SHORT price={price:.2f} pnl={pnl:.2f} ({pnl_pct:.2f}%) reason={reason}")
        self.position = None
        self.against_candle_count = 0

    # ==========================================================
    # HELPERS
    # ==========================================================
    def _calculate_stop_pct(self, volatility_pct):
        dynamic = volatility_pct * VOL_STOP_MULTIPLIER
        return max(MIN_STOP_PCT, min(dynamic, MAX_STOP_PCT))

    def _calculate_leverage(self, regime):
        base = LEVERAGE_INITIAL
        if self.consecutive_wins > 0:
            base = min(LEVERAGE_INITIAL + self.consecutive_wins * LEVERAGE_STEP, LEVERAGE_MAX)
        return base

    def update_candle_context(self, candle_return, volatility):
        if not self.position:
            return
        self.against_candle_count = self.against_candle_count + 1 if candle_return > 0 else 0
        self.recent_returns.append(candle_return)
        self.volatility_history.append(volatility)

    @abstractmethod
    def _on_open(self, symbol, size, price, leverage):
        pass

    @abstractmethod
    def _on_close(self, size, price, pnl):
        pass