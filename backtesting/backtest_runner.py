import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

from trading.position import Position
from core.enums import OrderType, SignalType
from config.settings import (
    BACKTEST_START_DATE, BACKTEST_END_DATE,
    BACKTEST_INITIAL_CAPITAL, BACKTEST_COMMISSION,
    MAX_RISK_PER_TRADE, DEFAULT_LEVERAGE,
    STOP_LOSS_PCT, TAKE_PROFIT_PCT,
    TRAILING_STOP_PCT, HARD_STOP_PCT,
    MAX_HOLD_SECONDS,TRADING_PAIRS
)


@dataclass
class BacktestTrade:
    pair: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    order_type: OrderType
    size: float
    leverage: float
    pnl: float
    pnl_pct: float
    commission: float
    hold_period: float  # in seconds
    exit_reason: str


class BacktestCapital:
    def __init__(self, initial_amount: float):
        self.initial = initial_amount
        self.current = initial_amount
        self.realized_pnl = 0.0
        self.commission_paid = 0.0
        
    def __float__(self):
        return self.current
    
    def update(self, pnl: float, commission: float = 0.0):
        self.current += pnl - commission
        self.realized_pnl += pnl
        self.commission_paid += commission


class BacktestPositionManager:
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.closed_trades: List[BacktestTrade] = []
        
    def has(self, pair: str) -> bool:
        return pair in self.positions
    
    def get(self, pair: str) -> Optional[Position]:
        return self.positions.get(pair)
    
    def open(self, position: Position):
        self.positions[position.pair] = position
    
    def close(self, pair: str) -> Optional[Position]:
        return self.positions.pop(pair, None)
    
    def count(self) -> int:
        return len(self.positions)


class BacktestRunner:
    def __init__(self, strategy, candles_df: pd.DataFrame):
        self.strategy = strategy
        self.candles = candles_df
        self.capital = BacktestCapital(BACKTEST_INITIAL_CAPITAL)
        self.positions = BacktestPositionManager()
        self.trades: List[BacktestTrade] = []
        
        # Performance tracking
        self.performance_metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0.0,
            'total_commission': 0.0,
            'max_drawdown': 0.0,
            'peak_equity': BACKTEST_INITIAL_CAPITAL,
            'current_drawdown': 0.0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'sharpe_ratio': 0.0,
            'sortino_ratio': 0.0
        }
        
        # Data validation
        self._validate_data()
    
    def _validate_data(self):
        """Validate candles data"""
        required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in self.candles.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Sort by timestamp
        self.candles = self.candles.sort_values('timestamp').reset_index(drop=True)
        
        print(f"[BACKTEST] Data validated: {len(self.candles)} candles")
        print(f"[BACKTEST] Date range: {self.candles['timestamp'].min()} to {self.candles['timestamp'].max()}")
    
    def run(self) -> Dict[str, Any]:
        """Run the backtest"""
        print(f"\n[BACKTEST] Starting backtest with ${BACKTEST_INITIAL_CAPITAL:.2f} capital")
        print("[BACKTEST]=" * 30)
        
        # Convert timestamp to datetime if needed
        if not isinstance(self.candles['timestamp'].iloc[0], datetime):
            self.candles['timestamp'] = pd.to_datetime(self.candles['timestamp'])
        
        # Iterate through candles
        for idx in range(len(self.candles)):
            if idx < 200:  # Need enough data for indicators
                continue
            
            current_candle = self.candles.iloc[idx]
            current_time = current_candle['timestamp']
            current_price = current_candle['close']
            
            # Build context for strategy
            context = self._build_context(idx)
            
            # Check exits first
            self._check_backtest_exits(current_time, current_price, idx)
            
            # Check if we can open new position
            if not self.positions.has(context['pair']):
                # Generate signal
                signal = self.strategy.generate(context)
                
                if signal and signal.signal_type == SignalType.TRADE:
                    # Check risk and open position
                    self._open_backtest_position(signal, current_time, current_price, idx)
            
            # Update equity tracking for drawdown calculation
            self._update_equity_tracking(current_price, idx)
        
        # Close any remaining positions at the end
        self._close_all_positions_at_end()
        
        # Calculate final metrics
        self._calculate_performance_metrics()
        
        # Generate report
        report = self._generate_report()
        
        return report
    
    def _build_context(self, idx: int) -> Dict[str, Any]:
        """Build context for strategy at given index"""
        current_candle = self.candles.iloc[idx]
        
        # Get previous candles for indicators
        window = self.candles.iloc[max(0, idx-200):idx+1]
        
        # Calculate basic indicators
        close_prices = window['close'].values
        
        # Simple moving averages
        sma_20 = close_prices[-20:].mean() if len(close_prices) >= 20 else close_prices.mean()
        sma_50 = close_prices[-50:].mean() if len(close_prices) >= 50 else close_prices.mean()
        
        # RSI
        rsi = self._calculate_rsi(close_prices[-15:]) if len(close_prices) >= 15 else 50
        
        # ATR
        atr = self._calculate_atr(window) if len(window) >= 14 else 0
        
        # Volume
        volume = current_candle['volume']
        avg_volume = window['volume'].mean()
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0
        
        # Determine trend
        if sma_20 > sma_50:
            trend = "UP"
        elif sma_20 < sma_50:
            trend = "DOWN"
        else:
            trend = "NEUTRAL"
        
        return {
            'pair': TRADING_PAIRS[0],  # Assuming single pair for simplicity
            'timestamp': current_candle['timestamp'],
            'price': float(current_candle['close']),
            'open': float(current_candle['open']),
            'high': float(current_candle['high']),
            'low': float(current_candle['low']),
            'volume': volume,
            'sma_20': sma_20,
            'sma_50': sma_50,
            'rsi': rsi,
            'atr': atr,
            'volume_ratio': volume_ratio,
            'trend': trend,
            'candles': window.to_dict('records')
        }
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else float('inf')
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        return float(rsi)
    
    def _calculate_atr(self, window: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(window) < period:
            return 0.0
        
        high = window['high'].values
        low = window['low'].values
        close = window['close'].values
        
        tr = np.zeros(len(window))
        for i in range(1, len(window)):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i-1])
            lc = abs(low[i] - close[i-1])
            tr[i] = max(hl, hc, lc)
        
        atr = tr[-period:].mean()
        return float(atr)
    
    def _open_backtest_position(self, signal, current_time: datetime, 
                               current_price: float, idx: int):
        """Open a position in backtest"""
        # Position sizing
        equity = float(self.capital)
        risk_amount = equity * MAX_RISK_PER_TRADE
        size = (risk_amount / current_price) * DEFAULT_LEVERAGE
        
        if size <= 0:
            return
        
        # Check if position would be too small
        position_value = size * current_price
        if position_value < 10.0:  # $10 minimum
            return
        
        # Create position
        position = Position(
            pair='SYN/USDT',
            order_type=signal.order_type,
            entry_price=current_price,
            size=size,
            leverage=DEFAULT_LEVERAGE,
        )
        position.open_ts = current_time.timestamp()
        position.open_idx = idx  # Track candle index
        
        self.positions.open(position)
        
        print(f"[BACKTEST] OPEN at {current_time}: {signal.order_type.value} "
              f"price={current_price:.4f} size={size:.4f}")
    
    def _check_backtest_exits(self, current_time: datetime, 
                             current_price: float, idx: int):
        """Check exit conditions for all positions"""
        for pair in list(self.positions.positions.keys()):
            pos = self.positions.get(pair)
            if not pos:
                continue
            
            hold_time = (current_time - datetime.fromtimestamp(pos.open_ts)).total_seconds()
            
            # Check various exit conditions
            exit_reason = None
            exit_price = current_price
            
            # 1. Stop loss
            if pos.order_type == OrderType.LONG:
                stop_loss = pos.entry_price * (1 - STOP_LOSS_PCT)
                if current_price <= stop_loss:
                    exit_reason = "STOP_LOSS"
            else:
                stop_loss = pos.entry_price * (1 + STOP_LOSS_PCT)
                if current_price >= stop_loss:
                    exit_reason = "STOP_LOSS"
            
            # 2. Take profit
            if not exit_reason:
                if pos.order_type == OrderType.LONG:
                    take_profit = pos.entry_price * (1 + TAKE_PROFIT_PCT)
                    if current_price >= take_profit:
                        exit_reason = "TAKE_PROFIT"
                else:
                    take_profit = pos.entry_price * (1 - TAKE_PROFIT_PCT)
                    if current_price <= take_profit:
                        exit_reason = "TAKE_PROFIT"
            
            # 3. Time exit
            if not exit_reason and hold_time >= MAX_HOLD_SECONDS:
                exit_reason = "TIME_EXIT"
            
            # 4. Trailing stop
            if not exit_reason:
                if pos.order_type == OrderType.LONG:
                    if pos.best_price is None:
                        pos.best_price = pos.entry_price
                    elif current_price > pos.best_price:
                        pos.best_price = current_price
                    
                    # Check if we've moved enough to activate trailing stop
                    if pos.best_price >= pos.entry_price * 1.015:  # 1.5% profit
                        trail_stop = pos.best_price * (1 - TRAILING_STOP_PCT)
                        if current_price <= trail_stop:
                            exit_reason = "TRAILING_STOP"
                else:
                    if pos.best_price is None:
                        pos.best_price = pos.entry_price
                    elif current_price < pos.best_price:
                        pos.best_price = current_price
                    
                    if pos.best_price <= pos.entry_price * 0.985:  # 1.5% profit
                        trail_stop = pos.best_price * (1 + TRAILING_STOP_PCT)
                        if current_price >= trail_stop:
                            exit_reason = "TRAILING_STOP"
            
            # Close position if exit condition met
            if exit_reason:
                self._close_backtest_position(pair, exit_price, exit_reason, 
                                            current_time, idx)
    
    def _close_backtest_position(self, pair: str, exit_price: float, 
                                reason: str, current_time: datetime, idx: int):
        """Close a position in backtest"""
        pos = self.positions.close(pair)
        if not pos:
            return
        
        # Calculate PnL
        if pos.order_type == OrderType.LONG:
            pnl = (exit_price - pos.entry_price) * pos.size
        else:
            pnl = (pos.entry_price - exit_price) * pos.size
        
        pnl_pct = (pnl / (pos.size * pos.entry_price / pos.leverage)) * 100
        
        # Calculate commission
        entry_value = pos.size * pos.entry_price
        exit_value = pos.size * exit_price
        commission = (entry_value + exit_value) * BACKTEST_COMMISSION
        
        # Update capital
        self.capital.update(pnl, commission)
        
        # Record trade
        trade = BacktestTrade(
            pair=pair,
            entry_time=datetime.fromtimestamp(pos.open_ts),
            exit_time=current_time,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            order_type=pos.order_type,
            size=pos.size,
            leverage=pos.leverage,
            pnl=pnl,
            pnl_pct=pnl_pct,
            commission=commission,
            hold_period=(current_time - datetime.fromtimestamp(pos.open_ts)).total_seconds(),
            exit_reason=reason
        )
        
        self.trades.append(trade)
        self.positions.closed_trades.append(trade)
        
        # Update performance metrics
        self.performance_metrics['total_trades'] += 1
        self.performance_metrics['total_pnl'] += pnl
        self.performance_metrics['total_commission'] += commission
        
        if pnl > 0:
            self.performance_metrics['winning_trades'] += 1
        else:
            self.performance_metrics['losing_trades'] += 1
        
        print(f"[BACKTEST] CLOSE at {current_time}: {pos.order_type.value} "
              f"price={exit_price:.4f} PnL=${pnl:.2f} ({reason})")
    
    def _close_all_positions_at_end(self):
        """Close all positions at the end of backtest"""
        if not self.positions.positions:
            return
        
        last_candle = self.candles.iloc[-1]
        last_time = last_candle['timestamp']
        last_price = last_candle['close']
        
        for pair in list(self.positions.positions.keys()):
            self._close_backtest_position(pair, last_price, "END_OF_DATA", 
                                        last_time, len(self.candles)-1)
    
    def _update_equity_tracking(self, current_price: float, idx: int):
        """Update equity tracking for drawdown calculation"""
        # Calculate current equity (capital + unrealized PnL)
        unrealized_pnl = 0
        for pos in self.positions.positions.values():
            if pos.order_type == OrderType.LONG:
                unrealized_pnl += (current_price - pos.entry_price) * pos.size
            else:
                unrealized_pnl += (pos.entry_price - current_price) * pos.size
        
        current_equity = float(self.capital) + unrealized_pnl
        
        # Update peak equity
        if current_equity > self.performance_metrics['peak_equity']:
            self.performance_metrics['peak_equity'] = current_equity
        
        # Calculate drawdown
        if self.performance_metrics['peak_equity'] > 0:
            drawdown = (self.performance_metrics['peak_equity'] - current_equity) / self.performance_metrics['peak_equity']
            self.performance_metrics['current_drawdown'] = drawdown
            
            if drawdown > self.performance_metrics['max_drawdown']:
                self.performance_metrics['max_drawdown'] = drawdown
    
    def _calculate_performance_metrics(self):
        """Calculate comprehensive performance metrics"""
        if not self.trades:
            return
        
        # Win rate
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        self.performance_metrics['win_rate'] = winning_trades / total_trades if total_trades > 0 else 0
        
        # Profit factor
        total_wins = sum(t.pnl for t in self.trades if t.pnl > 0)
        total_losses = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        self.performance_metrics['profit_factor'] = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Sharpe ratio (simplified)
        returns = [t.pnl_pct / 100 for t in self.trades]  # Convert to decimal
        if returns:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            self.performance_metrics['sharpe_ratio'] = avg_return / std_return * np.sqrt(252) if std_return > 0 else 0
            
            # Sortino ratio (only downside deviation)
            downside_returns = [r for r in returns if r < 0]
            downside_std = np.std(downside_returns) if downside_returns else 0
            self.performance_metrics['sortino_ratio'] = avg_return / downside_std * np.sqrt(252) if downside_std > 0 else 0
    
    def _generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive backtest report"""
        if not self.trades:
            return {"error": "No trades executed"}
        
        # Calculate final return
        final_return_pct = ((float(self.capital) - BACKTEST_INITIAL_CAPITAL) / BACKTEST_INITIAL_CAPITAL) * 100
        
        # Group trades by month
        trades_by_month = {}
        for trade in self.trades:
            month_key = trade.entry_time.strftime("%Y-%m")
            if month_key not in trades_by_month:
                trades_by_month[month_key] = []
            trades_by_month[month_key].append(trade)
        
        # Calculate monthly returns
        monthly_returns = {}
        for month, month_trades in trades_by_month.items():
            month_pnl = sum(t.pnl for t in month_trades)
            monthly_returns[month] = {
                'trades': len(month_trades),
                'pnl': month_pnl,
                'return_pct': (month_pnl / BACKTEST_INITIAL_CAPITAL) * 100
            }
        
        # Calculate trade statistics
        win_trades = [t for t in self.trades if t.pnl > 0]
        loss_trades = [t for t in self.trades if t.pnl <= 0]
        
        avg_win = np.mean([t.pnl for t in win_trades]) if win_trades else 0
        avg_loss = np.mean([t.pnl for t in loss_trades]) if loss_trades else 0
        avg_win_pct = np.mean([t.pnl_pct for t in win_trades]) if win_trades else 0
        avg_loss_pct = np.mean([t.pnl_pct for t in loss_trades]) if loss_trades else 0
        
        # Best and worst trade
        best_trade = max(self.trades, key=lambda t: t.pnl) if self.trades else None
        worst_trade = min(self.trades, key=lambda t: t.pnl) if self.trades else None
        
        # Exit reason analysis
        exit_reasons = {}
        for trade in self.trades:
            if trade.exit_reason not in exit_reasons:
                exit_reasons[trade.exit_reason] = {'count': 0, 'total_pnl': 0}
            exit_reasons[trade.exit_reason]['count'] += 1
            exit_reasons[trade.exit_reason]['total_pnl'] += trade.pnl
        
        # Create report
        report = {
            'summary': {
                'initial_capital': BACKTEST_INITIAL_CAPITAL,
                'final_capital': float(self.capital),
                'total_return': float(self.capital) - BACKTEST_INITIAL_CAPITAL,
                'total_return_pct': final_return_pct,
                'annualized_return_pct': final_return_pct * (365 / ((self.candles['timestamp'].max() - self.candles['timestamp'].min()).days or 1)),
                'total_trades': len(self.trades),
                'total_commission': self.performance_metrics['total_commission']
            },
            'performance': {
                'win_rate': self.performance_metrics['win_rate'],
                'profit_factor': self.performance_metrics['profit_factor'],
                'sharpe_ratio': self.performance_metrics['sharpe_ratio'],
                'sortino_ratio': self.performance_metrics['sortino_ratio'],
                'max_drawdown': self.performance_metrics['max_drawdown'],
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'avg_win_pct': avg_win_pct,
                'avg_loss_pct': avg_loss_pct,
                'largest_win': best_trade.pnl if best_trade else 0,
                'largest_loss': worst_trade.pnl if worst_trade else 0
            },
            'trade_analysis': {
                'winning_trades': len(win_trades),
                'losing_trades': len(loss_trades),
                'avg_trade_duration': np.mean([t.hold_period for t in self.trades]) if self.trades else 0,
                'avg_trade_return_pct': np.mean([t.pnl_pct for t in self.trades]) if self.trades else 0,
                'exit_reasons': exit_reasons
            },
            'monthly_returns': monthly_returns,
            'trades': [
                {
                    'entry_time': t.entry_time.isoformat(),
                    'exit_time': t.exit_time.isoformat(),
                    'side': t.order_type.value,
                    'entry_price': t.entry_price,
                    'exit_price': t.exit_price,
                    'size': t.size,
                    'leverage': t.leverage,
                    'pnl': t.pnl,
                    'pnl_pct': t.pnl_pct,
                    'commission': t.commission,
                    'hold_period': t.hold_period,
                    'exit_reason': t.exit_reason
                }
                for t in self.trades[-100:]  # Last 100 trades only
            ]
        }
        
        # Print summary
        print("\n" + "="*60)
        print("BACKTEST COMPLETE")
        print("="*60)
        print(f"Initial Capital: ${BACKTEST_INITIAL_CAPITAL:.2f}")
        print(f"Final Capital: ${float(self.capital):.2f}")
        print(f"Total Return: ${float(self.capital) - BACKTEST_INITIAL_CAPITAL:.2f} ({final_return_pct:.1f}%)")
        print(f"Total Trades: {len(self.trades)}")
        print(f"Win Rate: {self.performance_metrics['win_rate']:.1%}")
        print(f"Profit Factor: {self.performance_metrics['profit_factor']:.2f}")
        print(f"Max Drawdown: {self.performance_metrics['max_drawdown']:.1%}")
        print(f"Sharpe Ratio: {self.performance_metrics['sharpe_ratio']:.2f}")
        print(f"Total Commission: ${self.performance_metrics['total_commission']:.2f}")
        print("="*60)
        
        return report
    
    def save_report(self, filename: str = "backtest_report.json"):
        """Save backtest report to file"""
        report = self._generate_report()
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"[BACKTEST] Report saved to {filename}")
        
        # Also save trades to CSV
        trades_df = pd.DataFrame([
            {
                'entry_time': t.entry_time,
                'exit_time': t.exit_time,
                'side': t.order_type.value,
                'entry_price': t.entry_price,
                'exit_price': t.exit_price,
                'size': t.size,
                'pnl': t.pnl,
                'pnl_pct': t.pnl_pct,
                'hold_seconds': t.hold_period,
                'exit_reason': t.exit_reason
            }
            for t in self.trades
        ])
        
        csv_filename = filename.replace('.json', '_trades.csv')
        trades_df.to_csv(csv_filename, index=False)
        print(f"[BACKTEST] Trades saved to {csv_filename}")