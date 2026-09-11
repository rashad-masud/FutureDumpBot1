# trading/ccxt_trade_executor_base.py

from abc import ABC, abstractmethod
from config.settings import (
    STARTING_CAPITAL,
    TAKER_FEE_PCT,
    RISK_PER_TRADE_PCT,
    REGIME_SIZE_MULTIPLIER,
    MIN_LEVERAGE,
    MAX_LEVERAGE,
    DUMP_VOLATILITY_REF,
    MAX_STOP_PCT,
    MIN_STOP_PCT,
    VOL_STOP_MULTIPLIER,
    MAX_TOTAL_EXPOSURE_PCT,
)

class CCXTTradeExecutorBase(ABC):
    def __init__(self):
        self.balance = STARTING_CAPITAL
        self.position = None              # "long" / "short"
        self.entry_price = None
        self.position_size = 0.0
        self.stop_pct = None
        self.leverage = None
        self.daily_pnl = 0.0

    # ---------- PUBLIC API ----------
    def execute(self, symbol, signal, price, regime, volatility_pct):
        side = signal.value

        # stop-first safety
        if self.position:
            self.check_stop(price)

        if self.position and self.position != side:
            self._close_position(price)

        if self.position == side:
            return

        self._open_position(symbol, side, price, regime, volatility_pct)

    def check_stop(self, price) -> bool:
        if not self.position:
            return False

        stop_price = self._get_stop_price()
        hit = (
            price <= stop_price if self.position == "long"
            else price >= stop_price
        )

        if hit:
            print(f"[STOP] {self.position.upper()} hit @ {price:.2f}")
            self._close_position(price)
            return True

        return False

    # ---------- CORE LOGIC ----------
    def _open_position(
        self,
        symbol,
        side,
        price,
        regime,
        volatility_pct,
        size_factor=1.0,
    ):
        stop_pct = self._calculate_stop_pct(volatility_pct)
        leverage = self._calculate_leverage(regime)

        stop_distance = price * stop_pct

        # --- risk sizing ---
        risk_amount = self.balance * RISK_PER_TRADE_PCT
        risk_amount *= size_factor

        size = (risk_amount * leverage) / stop_distance
        notional = size * price
        fee = notional * TAKER_FEE_PCT
        required_margin = notional / leverage

        if required_margin + fee > self.balance:
            print(
                f"[EXECUTOR] insufficient margin "
                f"balance={self.balance:.2f} "
                f"required={required_margin + fee:.2f}"
            )
            return

        # --- commit ---
        self.balance -= fee
        self.position = side
        self.entry_price = price
        self.position_size = size
        self.stop_pct = stop_pct
        self.leverage = leverage

        self._on_open(symbol, side, size, price, leverage)

    # ---------- HELPERS ----------
    def _calculate_pnl(self, price):
        if self.position == "long":
            return (price - self.entry_price) * self.position_size
        return (self.entry_price - price) * self.position_size

    def _get_stop_price(self):
        if self.position == "long":
            return self.entry_price * (1 - self.stop_pct)
        return self.entry_price * (1 + self.stop_pct)

    def _calculate_stop_pct(self, volatility_pct):
        dynamic = volatility_pct * VOL_STOP_MULTIPLIER
        return max(MIN_STOP_PCT, min(dynamic, MAX_STOP_PCT))

    def _calculate_leverage(self, regime, volatility_pct):
        if regime != "dump":
            return MIN_LEVERAGE

        scale = min(volatility_pct / DUMP_VOLATILITY_REF, 1.0)
        lev = MIN_LEVERAGE + scale * (MAX_LEVERAGE - MIN_LEVERAGE)
        return round(min(max(lev, MIN_LEVERAGE), MAX_LEVERAGE), 2)

    # ---------- ABSTRACT HOOKS ----------
    @abstractmethod
    def _on_open(self, symbol, side, size, price, leverage):
        pass

    @abstractmethod
    def _on_close(self, side, size, price, pnl):
        pass
