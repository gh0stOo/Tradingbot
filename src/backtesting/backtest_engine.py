"""Backtesting Engine - Test strategies on historical data"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging

from data.database import Database
from trading.indicators import Indicators
from trading.regime_detector import RegimeDetector
from trading.strategies import Strategies
from trading.risk_manager import RiskManager
from trading.slippage_model import SlippageModel
from trading.bot import TradingBot

logger = logging.getLogger(__name__)


class BacktestPosition:
    """Represents a position during backtesting"""
    
    def __init__(
        self,
        trade_id: int,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        entry_time: datetime,
        stop_loss: float,
        take_profit: float,
        commission_rate: float = 0.001  # 0.1% default
    ):
        self.trade_id = trade_id
        self.symbol = symbol
        self.side = side
        self.entry_price = entry_price
        self.quantity = quantity
        self.entry_time = entry_time
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.commission_rate = commission_rate
        self.exit_price: Optional[float] = None
        self.exit_time: Optional[datetime] = None
        self.exit_reason: Optional[str] = None
        self.realized_pnl: Optional[float] = None
        
    def close(self, exit_price: float, exit_time: datetime, exit_reason: str) -> None:
        """Close the position and calculate PnL"""
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.exit_reason = exit_reason
        
        # Calculate PnL
        if self.side == "Buy":
            price_diff = exit_price - self.entry_price
        else:  # Sell
            price_diff = self.entry_price - exit_price
        
        # Gross PnL
        gross_pnl = price_diff * self.quantity
        
        # Commission costs (entry + exit)
        entry_commission = self.entry_price * self.quantity * self.commission_rate
        exit_commission = exit_price * self.quantity * self.commission_rate
        total_commission = entry_commission + exit_commission
        
        # Net PnL
        self.realized_pnl = gross_pnl - total_commission
    
    def check_exit(self, current_price: float, current_time: datetime) -> Optional[str]:
        """Check if exit conditions are met"""
        if self.side == "Buy":
            if current_price <= self.stop_loss:
                return "Stop Loss"
            elif current_price >= self.take_profit:
                return "Take Profit"
        else:  # Sell
            if current_price >= self.stop_loss:
                return "Stop Loss"
            elif current_price <= self.take_profit:
                return "Take Profit"
        return None


class BacktestEngine:
    """Main backtesting engine"""
    
    def __init__(
        self,
        config: Dict[str, Any],
        initial_equity: float = 10000.0,
        commission_rate: float = 0.001,  # 0.1% default
        slippage_rate: float = 0.0002,  # 0.02% default
        use_dynamic_slippage: bool = True
    ):
        """
        Initialize Backtest Engine
        
        Args:
            config: Trading bot configuration
            initial_equity: Starting equity
            commission_rate: Commission rate (0.001 = 0.1%)
            slippage_rate: Slippage rate (0.0002 = 0.02%)
            use_dynamic_slippage: Whether to use live slippage model
        """
        self.config = config
        self.initial_equity = initial_equity
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.use_dynamic_slippage = use_dynamic_slippage
        
        # Initialize components
        self.indicators_calc = Indicators()
        self.regime_detector = RegimeDetector()
        self.strategies = Strategies(config)
        self.risk_manager = RiskManager(config, data_collector=None)
        self.slippage_model = SlippageModel() if use_dynamic_slippage else None
        
        # Backtest state
        self.equity = initial_equity
        self.positions: Dict[int, BacktestPosition] = {}
        self.closed_trades: List[BacktestPosition] = []
        self.trade_id_counter = 1
        self.equity_history: List[Tuple[datetime, float]] = []
    
    def prepare_data(self, klines: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare historical data for backtesting
        
        Args:
            klines: DataFrame with OHLCV data (columns: timestamp, open, high, low, close, volume)
            
        Returns:
            DataFrame with indicators added
        """
        df = klines.copy()
        
        # Ensure proper column names
        if 'timestamp' not in df.columns and df.index.name == 'timestamp':
            df = df.reset_index()
        
        # Sort by timestamp
        df = df.sort_values('timestamp')
        
        # Calculate indicators
        indicators_dict = self.indicators_calc.calculate_all(df)
        
        # Add indicators to dataframe
        for key, value in indicators_dict.items():
            if isinstance(value, (int, float)):
                df[key] = value
            elif isinstance(value, pd.Series):
                df[key] = value.values if len(value) == len(df) else value.iloc[-1]
        
        return df
    
    def simulate_order(
        self,
        symbol: str,
        side: str,
        price: float,
        quantity: float,
        volume_24h_usd: Optional[float] = None,
        volatility: Optional[float] = None,
        asset_type: str = "linear"
    ) -> float:
        """
        Simulate order execution with slippage
        
        Args:
            symbol: Trading symbol
            side: Buy or Sell
            price: Target price
            quantity: Order quantity
            volume_24h_usd: Estimated 24h notional volume for slippage model
            volatility: Estimated volatility
            asset_type: Instrument type (default linear)
            
        Returns:
            Executed price (with slippage)
        """
        if self.use_dynamic_slippage and self.slippage_model:
            slippage = self.slippage_model.calculate_slippage(
                price=price,
                order_size_usd=quantity * price,
                volume_24h_usd=volume_24h_usd,
                side=side,
                volatility=volatility,
                asset_type=asset_type
            )
            return price + slippage if side == "Buy" else price - slippage
        
        # Fallback fixed slippage
        if side == "Buy":
            return price * (1 + self.slippage_rate)
        return price * (1 - self.slippage_rate)
    
    def calculate_position_size(
        self,
        equity: float,
        price: float,
        atr: float,
        side: str,
        confidence: float
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate position size using risk manager
        
        Args:
            equity: Current equity
            price: Entry price
            atr: Average True Range
            side: Buy or Sell
            confidence: Signal confidence
            
        Returns:
            Position size details or None
        """
        return self.risk_manager.calculate_position_size(
            equity=equity,
            price=price,
            atr=atr,
            side=side,
            confidence=confidence,
            qty_step=0.001,  # Default
            min_order_qty=0.001  # Default
        )
    
    def run_backtest(
        self,
        symbol: str,
        klines: pd.DataFrame,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Run backtest on historical data
        
        Args:
            symbol: Trading symbol
            klines: Historical kline data
            start_date: Start date (optional)
            end_date: End date (optional)
            
        Returns:
            Backtest results dictionary
        """
        # Prepare data
        df = self.prepare_data(klines)
        
        # Filter by date range if provided
        if start_date:
            df = df[df['timestamp'] >= start_date]
        if end_date:
            df = df[df['timestamp'] <= end_date]
        
        # Reset state
        self.equity = self.initial_equity
        self.positions = {}
        self.closed_trades = []
        self.trade_id_counter = 1
        self.equity_history = [(df.iloc[0]['timestamp'], self.initial_equity)]
        
        # Iterate through data
        for i in range(50, len(df)):  # Start at 50 to have enough data for indicators
            current_row = df.iloc[i]
            current_time = current_row['timestamp']
            current_price = current_row['close']
            window_start = max(0, i - 1440)  # Approximate last 24h on 1m data
            window_df = df.iloc[window_start:i+1]
            volume_24h_usd = float((window_df['volume'] * window_df['close']).sum()) if not window_df.empty else None
            volatility = float(window_df['close'].pct_change().std()) if len(window_df) > 1 else None
            
            # Update equity history
            self.equity_history.append((current_time, self.equity))
            
            # Check existing positions for exits
            positions_to_close = []
            for trade_id, position in list(self.positions.items()):
                exit_reason = position.check_exit(current_price, current_time)
                if exit_reason:
                    # Execute exit with slippage
                    exit_price = self.simulate_order(
                        position.symbol,
                        "Sell" if position.side == "Buy" else "Buy",
                        current_price,
                        position.quantity,
                        volume_24h_usd=volume_24h_usd,
                        volatility=volatility
                    )
                    position.close(exit_price, current_time, exit_reason)
                    positions_to_close.append(trade_id)
            
            # Close positions
            for trade_id in positions_to_close:
                position = self.positions.pop(trade_id)
                self.closed_trades.append(position)
                # Update equity
                if position.realized_pnl:
                    self.equity += position.realized_pnl
            
            # Skip if we already have open position (simple strategy: one position at a time)
            if self.positions:
                continue
            
            # Get indicators for current row
            indicators = {}
            for col in df.columns:
                if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
                    indicators[col] = current_row.get(col, 0)
            
            # Detect regime
            regime = self.regime_detector.detect_regime(indicators, current_price)
            
            # Run strategies
            candles_m1 = df.iloc[:i+1]
            candles_m5 = candles_m1  # For simplified backtest reuse same data
            candles_m15 = candles_m1
            strategy_signals = self.strategies.run_all_strategies(
                indicators=indicators,
                regime=regime,
                price=current_price,
                candles_m1=candles_m1,
                candles_m5=candles_m5,
                candles_m15=candles_m15
            )
            
            # Simple ensemble decision (take first signal with confidence > 0.6)
            signal = None
            for strat_signal in strategy_signals:
                if strat_signal and strat_signal.get('confidence', 0) > 0.6:
                    signal = strat_signal
                    break
            
            if not signal:
                continue
            
            # Calculate position size
            atr = indicators.get('atr', current_price * 0.02)  # Fallback ATR
            position_data = self.calculate_position_size(
                equity=self.equity,
                price=current_price,
                atr=atr,
                side=signal['side'],
                confidence=signal.get('confidence', 0.7)
            )
            
            if not position_data:
                continue
            
            # Simulate entry order
            entry_price = self.simulate_order(
                symbol,
                signal['side'],
                current_price,
                position_data['qty'],
                volume_24h_usd=volume_24h_usd,
                volatility=volatility
            )
            
            # Create position
            position = BacktestPosition(
                trade_id=self.trade_id_counter,
                symbol=symbol,
                side=signal['side'],
                entry_price=entry_price,
                quantity=position_data['qty'],
                entry_time=current_time,
                stop_loss=position_data['stopLoss'],
                take_profit=position_data['takeProfit'],
                commission_rate=self.commission_rate
            )
            
            self.positions[self.trade_id_counter] = position
            self.trade_id_counter += 1
            
            # Deduct commission from equity
            entry_commission = entry_price * position_data['qty'] * self.commission_rate
            self.equity -= entry_commission
        
        # Close any remaining positions at end
        final_price = df.iloc[-1]['close']
        final_time = df.iloc[-1]['timestamp']
        final_window = df.iloc[max(0, len(df) - 1440):]
        final_volume_24h_usd = float((final_window['volume'] * final_window['close']).sum()) if not final_window.empty else None
        final_volatility = float(final_window['close'].pct_change().std()) if len(final_window) > 1 else None
        for trade_id, position in list(self.positions.items()):
            exit_price = self.simulate_order(
                position.symbol,
                "Sell" if position.side == "Buy" else "Buy",
                final_price,
                position.quantity,
                volume_24h_usd=final_volume_24h_usd,
                volatility=final_volatility
            )
            position.close(exit_price, final_time, "End of Backtest")
            self.closed_trades.append(position)
            if position.realized_pnl:
                self.equity += position.realized_pnl
        
        # Calculate metrics
        return self.calculate_metrics()
    
    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics from backtest results"""
        if not self.closed_trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "profit_factor": 0.0
            }
        
        # Basic stats
        total_trades = len(self.closed_trades)
        winning_trades = [t for t in self.closed_trades if t.realized_pnl and t.realized_pnl > 0]
        losing_trades = [t for t in self.closed_trades if t.realized_pnl and t.realized_pnl <= 0]
        
        win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
        
        total_pnl = sum(t.realized_pnl for t in self.closed_trades if t.realized_pnl)
        gross_profit = sum(t.realized_pnl for t in winning_trades if t.realized_pnl)
        gross_loss = abs(sum(t.realized_pnl for t in losing_trades if t.realized_pnl))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
        
        # Calculate Sharpe Ratio (simplified)
        if len(self.closed_trades) > 1:
            returns = [t.realized_pnl / self.initial_equity for t in self.closed_trades if t.realized_pnl]
            if returns:
                mean_return = np.mean(returns)
                std_return = np.std(returns)
                sharpe_ratio = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0.0
            else:
                sharpe_ratio = 0.0
        else:
            sharpe_ratio = 0.0
        
        # Calculate Max Drawdown
        equity_values = [eq for _, eq in self.equity_history]
        if equity_values:
            peak = equity_values[0]
            max_drawdown = 0.0
            for equity in equity_values:
                if equity > peak:
                    peak = equity
                drawdown = (peak - equity) / peak if peak > 0 else 0.0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
        else:
            max_drawdown = 0.0
        
        return {
            "total_trades": total_trades,
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": round(win_rate * 100, 2),
            "total_pnl": round(total_pnl, 2),
            "final_equity": round(self.equity, 2),
            "return_pct": round((self.equity - self.initial_equity) / self.initial_equity * 100, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "profit_factor": round(profit_factor, 2),
            "average_win": round(np.mean([t.realized_pnl for t in winning_trades if t.realized_pnl]), 2) if winning_trades else 0.0,
            "average_loss": round(np.mean([t.realized_pnl for t in losing_trades if t.realized_pnl]), 2) if losing_trades else 0.0,
            "largest_win": round(max([t.realized_pnl for t in winning_trades if t.realized_pnl]), 2) if winning_trades else 0.0,
            "largest_loss": round(min([t.realized_pnl for t in losing_trades if t.realized_pnl]), 2) if losing_trades else 0.0
        }

