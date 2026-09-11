from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class Position:
    trade_id: int
    symbol: str
    entry_price: float
    size: float
    leverage: float
    stop_pct: float
    opened_at: float
    open_candle_id: Optional[int] = None
    open_tick_id: Optional[int] = None
    best_price: Optional[float] = None
    trail_active: bool = False

    def __post_init__(self):
        if self.best_price is None:
            self.best_price = self.entry_price

    def pnl(self, current_price: float) -> float:
        # Short only: profit when price drops
        return (self.entry_price - current_price) * self.size

    def pnl_pct(self, current_price: float) -> float:
        return ((self.entry_price - current_price) / self.entry_price) * 100

    def update_stats(self, current_price: float):
        current_pnl = self.pnl(current_price)
        if current_pnl > self.max_profit:
            self.max_profit = current_pnl
        current_drawdown = max(0, self.max_profit - current_pnl)
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown
        if current_price < self.best_price:          # for shorts, best is lowest price
            self.best_price = current_price
        self.last_updated = datetime.utcnow().timestamp()

    def get_position_value(self, current_price: float) -> float:
        return self.size * current_price

    def get_margin_used(self) -> float:
        return (self.size * self.entry_price) / self.leverage

    def to_dict(self) -> dict:
        return {
            'trade_id': self.trade_id,
            'symbol': self.symbol,
            'entry_price': self.entry_price,
            'size': self.size,
            'leverage': self.leverage,
            'stop_pct': self.stop_pct,
            'best_price': self.best_price,
            'open_ts': self.opened_at,
        }