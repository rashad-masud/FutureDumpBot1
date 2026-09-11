from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from core.enums import OrderType

@dataclass
class Position:
    pair: str
    order_type: OrderType
    entry_price: float
    size: float
    leverage: float
    
    # Optional fields with defaults
    best_price: Optional[float] = None
    open_ts: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    atr: float = 0.0  # Average True Range for volatility-based stops
    risk_reward_ratio: float = 2.0
    
    # Tracking fields
    max_profit: float = 0.0
    max_drawdown: float = 0.0
    last_updated: float = field(default_factory=lambda: datetime.utcnow().timestamp())
    
    def __post_init__(self):
        """Initialize derived fields after creation"""
        if self.best_price is None:
            self.best_price = self.entry_price
        
        # Calculate stop loss and take profit if not provided
        if self.stop_loss is None:
            if self.order_type == OrderType.LONG:
                self.stop_loss = self.entry_price * 0.98  # 2% stop loss
                self.take_profit = self.entry_price * 1.04  # 4% take profit (2:1 RR)
            else:
                self.stop_loss = self.entry_price * 1.02
                self.take_profit = self.entry_price * 0.96
    
    def pnl(self, current_price: float) -> float:
        """Calculate PnL based on current price"""
        if self.order_type == OrderType.LONG:
            return (current_price - self.entry_price) * self.size
        else:
            return (self.entry_price - current_price) * self.size
    
    def pnl_pct(self, current_price: float) -> float:
        """Calculate PnL as percentage of entry"""
        if self.order_type == OrderType.LONG:
            return ((current_price - self.entry_price) / self.entry_price) * 100
        else:
            return ((self.entry_price - current_price) / self.entry_price) * 100
    
    def update_stats(self, current_price: float):
        """Update position statistics with current price"""
        current_pnl = self.pnl(current_price)
        
        # Update max profit
        if current_pnl > self.max_profit:
            self.max_profit = current_pnl
        
        # Update max drawdown
        current_drawdown = max(0, self.max_profit - current_pnl)
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown
        
        # Update best price for trailing stops
        if self.order_type == OrderType.LONG:
            if current_price > self.best_price:
                self.best_price = current_price
        else:
            if current_price < self.best_price:
                self.best_price = current_price
        
        self.last_updated = datetime.utcnow().timestamp()
    
    def get_position_value(self, current_price: float) -> float:
        """Calculate current position value"""
        return self.size * current_price
    
    def get_margin_used(self) -> float:
        """Calculate margin used for this position"""
        return (self.size * self.entry_price) / self.leverage
    
    def to_dict(self) -> dict:
        """Convert position to dictionary"""
        return {
            'pair': self.pair,
            'order_type': self.order_type.value,
            'entry_price': self.entry_price,
            'size': self.size,
            'leverage': self.leverage,
            'best_price': self.best_price,
            'open_ts': self.open_ts,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit
        }