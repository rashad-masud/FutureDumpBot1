from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Position:
    trade_id: int
    symbol: str
    side: str
    entry_price: float
    size: float
    leverage: float
    stop_loss: float
    initial_stop_distance: float
    atr: float
    trail_stop: float | None = None
    best_price: float | None = None
    opened_at: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    open_candle_id: int | None = None
    open_tick_id: int | None = None
    trail_active: bool = False
    entry_fee: float = 0.0

    def __post_init__(self):
        if self.best_price is None:
            self.best_price = self.entry_price

    def pnl(self, current_price: float) -> float:
        if self.side == "long":
            return (current_price - self.entry_price) * self.size
        return (self.entry_price - current_price) * self.size

    def pnl_pct(self, current_price: float) -> float:
        if self.side == "long":
            return (current_price - self.entry_price) / self.entry_price * 100.0
        return (self.entry_price - current_price) / self.entry_price * 100.0

    def get_position_value(self, current_price: float) -> float:
        return self.size * current_price

    def get_margin_used(self) -> float:
        return self.get_position_value(self.entry_price) / self.leverage
