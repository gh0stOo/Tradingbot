"""Walk-Forward Analysis for Backtesting"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from backtesting.backtest_engine import BacktestEngine

logger = logging.getLogger(__name__)


class WalkForwardAnalysis:
    """Walk-Forward Analysis for robust backtesting"""
    
    def __init__(
        self,
        config: Dict[str, Any],
        train_period_days: int = 180,  # 6 months training
        test_period_days: int = 30,  # 1 month testing
        step_days: int = 30  # Step forward 1 month
    ):
        """
        Initialize Walk-Forward Analysis
        
        Args:
            config: Trading bot configuration
            train_period_days: Training period in days
            test_period_days: Testing period in days
            step_days: Step size in days between windows
        """
        self.config = config
        self.train_period_days = train_period_days
        self.test_period_days = test_period_days
        self.step_days = step_days
    
    def run_walk_forward(
        self,
        symbol: str,
        klines,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Run walk-forward analysis
        
        Args:
            symbol: Trading symbol
            klines: Historical kline data
            start_date: Analysis start date
            end_date: Analysis end date
            
        Returns:
            Walk-forward analysis results
        """
        results = []
        current_start = start_date
        
        while current_start + timedelta(days=self.train_period_days + self.test_period_days) <= end_date:
            train_start = current_start
            train_end = train_start + timedelta(days=self.train_period_days)
            test_start = train_end
            test_end = test_start + timedelta(days=self.test_period_days)
            
            logger.info(
                f"Walk-forward window: Train {train_start.date()} to {train_end.date()}, "
                f"Test {test_start.date()} to {test_end.date()}"
            )
            
            # Run backtest on test period
            engine = BacktestEngine(self.config)
            test_results = engine.run_backtest(
                symbol=symbol,
                klines=klines,
                start_date=test_start,
                end_date=test_end
            )
            
            results.append({
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "metrics": test_results
            })
            
            # Step forward
            current_start += timedelta(days=self.step_days)
        
        # Aggregate results
        if not results:
            return {"error": "No results generated"}
        
        # Calculate average metrics
        total_trades = sum(r["metrics"]["total_trades"] for r in results)
        avg_win_rate = sum(r["metrics"]["win_rate"] for r in results) / len(results) if results else 0.0
        avg_sharpe = sum(r["metrics"]["sharpe_ratio"] for r in results) / len(results) if results else 0.0
        avg_max_dd = sum(r["metrics"]["max_drawdown"] for r in results) / len(results) if results else 0.0
        avg_profit_factor = sum(r["metrics"]["profit_factor"] for r in results) / len(results) if results else 0.0
        
        return {
            "windows": len(results),
            "total_trades": total_trades,
            "average_win_rate": round(avg_win_rate, 2),
            "average_sharpe_ratio": round(avg_sharpe, 2),
            "average_max_drawdown": round(avg_max_dd, 2),
            "average_profit_factor": round(avg_profit_factor, 2),
            "window_results": results
        }

