# utils/trade_logger.py
import csv
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from config.settings import TRADE_CSV_FILE

class TradeAction(Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"

class TradeDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class CloseReason(Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    MANUAL = "MANUAL"
    TRAILING_STOP = "TRAILING_STOP"
    SIGNAL_REVERSAL = "SIGNAL_REVERSAL"
    RISK_MANAGEMENT = "RISK_MANAGEMENT"
    TIME_BASED = "TIME_BASED"
    EMERGENCY = "EMERGENCY"
    SHUTDOWN = "SHUTDOWN"

@dataclass
class TradeRecord:
    """Data class for trade records"""
    timestamp: str
    trade_id: str
    pair: str
    action: str
    direction: str
    size: float
    price: float
    leverage: int = 1
    pnl: float = 0.0
    pnl_pct: float = 0.0
    pnl_usdt: float = 0.0
    reason: str = ""
    position_size_usdt: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    entry_time: str = ""
    exit_time: str = ""
    duration_seconds: float = 0.0
    strategy: str = ""
    risk_level: str = "MEDIUM"
    fees: float = 0.0
    notes: str = ""

class TradeLogger:
    """Handles CSV logging for trades"""
    
    def __init__(self, log_file_path: Path):
        self.log_file = log_file_path
        self.logger = logging.getLogger(self.__class__.__name__)
        self._init_log_file()
    
    def _init_log_file(self):
        """Initialize the CSV file with headers if it doesn't exist"""
        TRADE_LOG_FIELDS = [
            'timestamp', 'trade_id', 'pair', 'action', 'direction', 
            'size', 'price', 'leverage', 'pnl', 'pnl_pct', 'pnl_usdt',
            'reason', 'position_size_usdt', 'stop_loss', 'take_profit',
            'entry_time', 'exit_time', 'duration_seconds', 'strategy',
            'risk_level', 'fees', 'notes'
        ]
        
        if not self.log_file.exists():
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=TRADE_LOG_FIELDS)
                writer.writeheader()
            self.logger.info(f"Initialized trade log: {self.log_file}")
    
    def log_trade(self, trade_record: TradeRecord):
        """Log a trade to CSV"""
        try:
            TRADE_LOG_FIELDS = [
                'timestamp', 'trade_id', 'pair', 'action', 'direction', 
                'size', 'price', 'leverage', 'pnl', 'pnl_pct', 'pnl_usdt',
                'reason', 'position_size_usdt', 'stop_loss', 'take_profit',
                'entry_time', 'exit_time', 'duration_seconds', 'strategy',
                'risk_level', 'fees', 'notes'
            ]
            
            # Convert dataclass to dict
            trade_dict = asdict(trade_record)
            
            # Ensure all fields are present
            for field in TRADE_LOG_FIELDS:
                if field not in trade_dict:
                    trade_dict[field] = ""
            
            # Write to CSV
            with open(self.log_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=TRADE_LOG_FIELDS)
                writer.writerow(trade_dict)
            
            # Also log to console
            if trade_record.action == TradeAction.OPEN.value:
                self.logger.info(
                    f"[OPEN] {trade_record.pair} {trade_record.direction} "
                    f"size={trade_record.size:.6f} price=${trade_record.price:.2f} "
                    f"lev={trade_record.leverage}x"
                )
            else:
                pnl_sign = "+" if trade_record.pnl >= 0 else ""
                self.logger.info(
                    f"[CLOSE] {trade_record.pair} PnL={pnl_sign}{trade_record.pnl:.2f} "
                    f"({pnl_sign}{trade_record.pnl_pct:.2f}%) reason={trade_record.reason}"
                )
                
        except Exception as e:
            self.logger.error(f"Failed to log trade: {e}")
    
    def get_trade_id(self, pair: str, timestamp: float) -> str:
        """Generate a unique trade ID"""
        timestamp_str = datetime.fromtimestamp(timestamp).strftime('%Y%m%d_%H%M%S')
        pair_simple = pair.replace('/', '').replace('-', '')
        return f"{pair_simple}_{timestamp_str}"
    
    def get_all_trades(self) -> list:
        """Read all trades from CSV"""
        try:
            with open(self.log_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                return list(reader)
        except Exception as e:
            self.logger.error(f"Failed to read trades: {e}")
            return []
    
    def get_trades_by_pair(self, pair: str) -> list:
        """Get all trades for a specific pair"""
        all_trades = self.get_all_trades()
        return [trade for trade in all_trades if trade.get('pair') == pair]
    
    def get_total_pnl(self) -> Dict[str, float]:
        """Calculate total P&L by pair"""
        all_trades = self.get_all_trades()
        pnl_by_pair = {}
        
        for trade in all_trades:
            pair = trade.get('pair', '')
            pnl = float(trade.get('pnl_usdt', 0))
            
            if pair not in pnl_by_pair:
                pnl_by_pair[pair] = 0.0
            pnl_by_pair[pair] += pnl
        
        return pnl_by_pair
    
    def get_stats(self) -> Dict[str, Any]:
        """Get trade statistics"""
        try:
            all_trades = self.get_all_trades()
            closed_trades = [t for t in all_trades if t.get('action') == 'CLOSE']
            
            if not closed_trades:
                return {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0.0,
                    'total_pnl': 0.0,
                    'largest_win': 0.0,
                    'largest_loss': 0.0
                }
            
            winning_trades = [t for t in closed_trades if float(t.get('pnl_usdt', 0)) > 0]
            losing_trades = [t for t in closed_trades if float(t.get('pnl_usdt', 0)) < 0]
            
            total_pnl = sum(float(t.get('pnl_usdt', 0)) for t in closed_trades)
            
            largest_win = max((float(t.get('pnl_usdt', 0)) for t in winning_trades), default=0.0)
            largest_loss = min((float(t.get('pnl_usdt', 0)) for t in losing_trades), default=0.0)
            
            win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0.0
            
            return {
                'total_trades': len(closed_trades),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'largest_win': largest_win,
                'largest_loss': largest_loss,
                'profit_factor': abs(sum(float(t.get('pnl_usdt', 0)) for t in winning_trades) / 
                                   sum(float(t.get('pnl_usdt', 0)) for t in losing_trades)) if losing_trades else float('inf')
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get stats: {e}")
            return {}