"""Backtest Runner for Genetic Algorithm Optimization"""

import copy
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
import logging

from backtesting.backtest_engine import BacktestEngine
from data.database import Database
from data.data_collector import DataCollector
from data.position_tracker import PositionTracker

logger = logging.getLogger(__name__)


class BacktestRunner:
    """
    Runs backtests on historical trades for fitness evaluation in genetic algorithm.
    
    Uses rolling window approach: last N trades from database.
    """
    
    def __init__(
        self,
        database_path: str,
        rolling_window_trades: int = 500,
        initial_equity: float = 10000.0
    ):
        """
        Initialize Backtest Runner
        
        Args:
            database_path: Path to SQLite database with historical trades
            rolling_window_trades: Number of recent trades to use for backtesting
            initial_equity: Initial equity for backtesting
        """
        self.database_path = database_path
        self.rolling_window_trades = rolling_window_trades
        self.initial_equity = initial_equity
        
        self.db = Database(database_path)
        self.data_collector = DataCollector(self.db)
        self.position_tracker = PositionTracker(self.db)
        
        logger.info(f"BacktestRunner initialized: window={rolling_window_trades} trades, equity={initial_equity}")
    
    def _prepare_historical_data_from_db(self) -> Optional[pd.DataFrame]:
        """
        Load historical trades from database and prepare klines
        
        Returns:
            DataFrame with historical trade data and required fields
        """
        try:
            # Get recent trades from database
            query = """
                SELECT 
                    trade_id, symbol, side, entry_price, exit_price, quantity,
                    stop_loss, take_profit, entry_time, exit_time,
                    realized_pnl, success, confidence, quality_score,
                    regime_type, strategies_used
                FROM trades
                WHERE exit_time IS NOT NULL
                ORDER BY entry_time DESC
                LIMIT ?
            """
            
            cursor = self.db.execute(query, (self.rolling_window_trades,))
            trades_data = cursor.fetchall()
            
            if not trades_data:
                logger.warning("No historical trades found in database")
                return None
            
            # Convert to DataFrame
            columns = [
                'trade_id', 'symbol', 'side', 'entry_price', 'exit_price', 'quantity',
                'stop_loss', 'take_profit', 'entry_time', 'exit_time',
                'realized_pnl', 'success', 'confidence', 'quality_score',
                'regime_type', 'strategies_used'
            ]
            
            df = pd.DataFrame(trades_data, columns=columns)
            df['entry_time'] = pd.to_datetime(df['entry_time'])
            df['exit_time'] = pd.to_datetime(df['exit_time'])
            
            # Sort by entry_time ascending
            df = df.sort_values('entry_time').reset_index(drop=True)
            
            logger.info(f"Loaded {len(df)} trades from database")
            return df
            
        except Exception as e:
            logger.error(f"Error loading historical data: {e}", exc_info=True)
            return None
    
    def run_backtest(
        self,
        config: Dict[str, Any],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Run backtest with given configuration
        
        Args:
            config: Trading bot configuration (may contain optimized parameters)
            start_date: Optional start date for backtest
            end_date: Optional end date for backtest
            
        Returns:
            Dictionary with performance metrics
        """
        try:
            # Load historical trades
            trades_df = self._prepare_historical_data_from_db()
            if trades_df is None or trades_df.empty:
                return {
                    "total_pnl": -float('inf'),
                    "win_rate": 0.0,
                    "sharpe_ratio": 0.0,
                    "max_drawdown": 1.0,
                    "profit_factor": 0.0,
                    "total_trades": 0
                }
            
            # Filter by date if provided
            if start_date:
                trades_df = trades_df[trades_df['entry_time'] >= start_date]
            if end_date:
                trades_df = trades_df[trades_df['entry_time'] <= end_date]
            
            if trades_df.empty:
                return {
                    "total_pnl": -float('inf'),
                    "win_rate": 0.0,
                    "sharpe_ratio": 0.0,
                    "max_drawdown": 1.0,
                    "profit_factor": 0.0,
                    "total_trades": 0
                }
            
            # Calculate metrics from historical trades
            total_trades = len(trades_df)
            winning_trades = trades_df[trades_df['success'] == True]
            losing_trades = trades_df[trades_df['success'] == False]
            
            total_pnl = trades_df['realized_pnl'].sum()
            win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0.0
            
            gross_profit = winning_trades['realized_pnl'].sum() if len(winning_trades) > 0 else 0.0
            gross_loss = abs(losing_trades['realized_pnl'].sum()) if len(losing_trades) > 0 else 1.0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
            
            # Calculate equity curve
            equity = self.initial_equity
            equity_curve = [equity]
            for _, trade in trades_df.iterrows():
                equity += trade['realized_pnl']
                equity_curve.append(equity)
            
            # Calculate max drawdown
            peak = self.initial_equity
            max_drawdown = 0.0
            for equity_point in equity_curve:
                if equity_point > peak:
                    peak = equity_point
                drawdown = (peak - equity_point) / peak if peak > 0 else 0.0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            
            # Calculate Sharpe Ratio (simplified - assumes daily returns)
            returns = np.diff(equity_curve) / equity_curve[:-1]
            if len(returns) > 1 and returns.std() > 0:
                sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252)  # Annualized
            else:
                sharpe_ratio = 0.0
            
            metrics = {
                "total_pnl": float(total_pnl),
                "win_rate": float(win_rate),
                "sharpe_ratio": float(sharpe_ratio),
                "max_drawdown": float(max_drawdown),
                "profit_factor": float(profit_factor),
                "total_trades": int(total_trades),
                "winning_trades": len(winning_trades),
                "losing_trades": len(losing_trades),
                "final_equity": float(equity_curve[-1]) if equity_curve else self.initial_equity
            }
            
            logger.debug(f"Backtest metrics: PnL={total_pnl:.2f}, WR={win_rate:.2%}, Sharpe={sharpe_ratio:.2f}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error running backtest: {e}", exc_info=True)
            return {
                "total_pnl": -float('inf'),
                "win_rate": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 1.0,
                "profit_factor": 0.0,
                "total_trades": 0
            }
    
    def create_fitness_function(
        self,
        base_config: Dict[str, Any],
        weights: Dict[str, float] = None
    ) -> Callable[[Dict[str, Any]], float]:
        """
        Create a fitness function for genetic algorithm
        
        Args:
            base_config: Base trading bot configuration
            weights: Weights for different metrics (default: equal weights)
                     Keys: "pnl", "win_rate", "sharpe", "drawdown", "profit_factor"
        
        Returns:
            Fitness function that takes parameter dict and returns fitness score
        """
        if weights is None:
            weights = {
                "sharpe": 0.4,
                "win_rate": 0.3,
                "profit_factor": 0.2,
                "drawdown": -0.1  # Negative because lower is better
            }
        
        def fitness_function(parameters: Dict[str, Any]) -> float:
            """
            Calculate fitness from parameters
            
            Args:
                parameters: Parameter dictionary (optimized values)
                
            Returns:
                Fitness score (higher is better)
            """
            # Merge parameters into config
            config = copy.deepcopy(base_config)
            
            # Apply parameters to config (depending on what's being optimized)
            # This is a simplified version - actual implementation would map
            # parameter names to config paths
            for key, value in parameters.items():
                # Example mappings (adjust based on actual parameter structure)
                if key.startswith("strategy_weight_"):
                    strategy_name = key.replace("strategy_weight_", "")
                    if "strategies" in config and strategy_name in config["strategies"]:
                        config["strategies"][strategy_name]["weight"] = value
                elif key.startswith("risk_"):
                    risk_param = key.replace("risk_", "")
                    if "risk" in config and risk_param in config["risk"]:
                        config["risk"][risk_param] = value
                elif key == "minConfidence":
                    if "ensemble" in config:
                        config["ensemble"]["minConfidence"] = value
                elif key == "minQualityScore":
                    if "ensemble" in config:
                        config["ensemble"]["minQualityScore"] = value
            
            # Run backtest
            metrics = self.run_backtest(config)
            
            # Calculate weighted fitness
            fitness = (
                weights["sharpe"] * metrics["sharpe_ratio"] +
                weights["win_rate"] * metrics["win_rate"] * 100 +  # Scale to 0-100
                weights["profit_factor"] * metrics["profit_factor"] +
                weights["drawdown"] * metrics["max_drawdown"] * 100  # Negative weight
            )
            
            # Penalty for insufficient trades
            if metrics["total_trades"] < 10:
                fitness *= 0.5  # Reduce fitness if too few trades
            
            return fitness
        
        return fitness_function

