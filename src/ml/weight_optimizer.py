"""Online Weight Optimizer for Strategy Weights"""

import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class WeightOptimizer:
    """
    Online Gradient Descent optimizer for strategy weights.
    
    Adjusts strategy weights based on rolling performance of recent trades.
    """
    
    def __init__(
        self,
        initial_weights: Dict[str, float],
        learning_rate: float = 0.01,
        rolling_window_trades: int = 50,
        min_weight: float = 0.0,
        max_weight: float = 2.0
    ):
        """
        Initialize Weight Optimizer
        
        Args:
            initial_weights: Initial strategy weights dict
            learning_rate: Learning rate for gradient descent (0.0-1.0)
            rolling_window_trades: Number of recent trades to consider
            min_weight: Minimum weight value
            max_weight: Maximum weight value
        """
        self.initial_weights = initial_weights.copy()
        self.current_weights = initial_weights.copy()
        self.learning_rate = learning_rate
        self.rolling_window_trades = rolling_window_trades
        self.min_weight = min_weight
        self.max_weight = max_weight
        
        # Track performance per strategy
        self.strategy_performance: Dict[str, List[float]] = {
            strategy: [] for strategy in initial_weights.keys()
        }
        
        logger.info(f"WeightOptimizer initialized: {len(initial_weights)} strategies, lr={learning_rate}")
    
    def update_from_trades(
        self,
        trades: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Update strategy weights based on recent trades
        
        Args:
            trades: List of trade dicts with 'strategies_used' and 'realized_pnl' keys
            
        Returns:
            Updated weights dict
        """
        if not trades:
            return self.current_weights
        
        # Use only recent trades
        recent_trades = trades[-self.rolling_window_trades:]
        
        # Calculate performance per strategy
        strategy_pnl: Dict[str, List[float]] = {
            strategy: [] for strategy in self.current_weights.keys()
        }
        
        for trade in recent_trades:
            strategies_used = trade.get("strategies_used", [])
            pnl = trade.get("realized_pnl", 0.0)
            success = trade.get("success", pnl > 0)
            
            # Distribute PnL to strategies used in this trade
            if strategies_used:
                pnl_per_strategy = pnl / len(strategies_used)
                for strategy in strategies_used:
                    if strategy in strategy_pnl:
                        strategy_pnl[strategy].append(pnl_per_strategy if success else -abs(pnl_per_strategy))
        
        # Calculate average performance per strategy
        strategy_avg_performance: Dict[str, float] = {}
        for strategy, pnl_list in strategy_pnl.items():
            if pnl_list:
                strategy_avg_performance[strategy] = np.mean(pnl_list)
            else:
                strategy_avg_performance[strategy] = 0.0
        
        # Update weights using gradient descent approach
        # Increase weight for strategies with positive performance
        # Decrease weight for strategies with negative performance
        for strategy in self.current_weights.keys():
            performance = strategy_avg_performance.get(strategy, 0.0)
            
            # Normalize performance to [-1, 1] range for gradient calculation
            # Use a sigmoid-like normalization
            normalized_performance = np.tanh(performance / 100.0)  # Adjust divisor based on typical PnL scale
            
            # Update weight: gradient = normalized_performance
            weight_change = self.learning_rate * normalized_performance
            
            new_weight = self.current_weights[strategy] + weight_change
            new_weight = np.clip(new_weight, self.min_weight, self.max_weight)
            
            self.current_weights[strategy] = new_weight
        
        # Store performance history
        for strategy, perf in strategy_avg_performance.items():
            self.strategy_performance[strategy].append(perf)
            # Keep only recent history
            if len(self.strategy_performance[strategy]) > self.rolling_window_trades:
                self.strategy_performance[strategy] = self.strategy_performance[strategy][-self.rolling_window_trades:]
        
        logger.debug(f"Updated weights: {self.current_weights}")
        
        return self.current_weights.copy()
    
    def get_weights(self) -> Dict[str, float]:
        """Get current strategy weights"""
        return self.current_weights.copy()
    
    def reset_weights(self) -> None:
        """Reset weights to initial values"""
        self.current_weights = self.initial_weights.copy()
        logger.info("Weights reset to initial values")
    
    def get_strategy_performance(self, strategy: str) -> List[float]:
        """Get performance history for a strategy"""
        return self.strategy_performance.get(strategy, []).copy()
    
    def get_all_performance_stats(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics for all strategies"""
        stats = {}
        for strategy, perf_list in self.strategy_performance.items():
            if perf_list:
                stats[strategy] = {
                    "mean": float(np.mean(perf_list)),
                    "std": float(np.std(perf_list)),
                    "min": float(np.min(perf_list)),
                    "max": float(np.max(perf_list)),
                    "current_weight": self.current_weights.get(strategy, 0.0)
                }
            else:
                stats[strategy] = {
                    "mean": 0.0,
                    "std": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "current_weight": self.current_weights.get(strategy, 0.0)
                }
        return stats


class OnlineLearningManager:
    """
    Manages online learning for strategy weights.
    
    Automatically updates weights based on trade performance.
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        data_collector: Any  # DataCollector instance
    ):
        """
        Initialize Online Learning Manager
        
        Args:
            config: Configuration dict
            data_collector: DataCollector instance for accessing trade data
        """
        self.config = config
        self.data_collector = data_collector
        
        # Get initial strategy weights from config
        strategies_config = config.get("strategies", {})
        initial_weights = {
            strategy_name: strategy_config.get("weight", 1.0)
            for strategy_name, strategy_config in strategies_config.items()
        }
        
        # Initialize weight optimizer
        online_config = config.get("ml", {}).get("onlineLearning", {})
        self.weight_optimizer = WeightOptimizer(
            initial_weights=initial_weights,
            learning_rate=online_config.get("learningRate", 0.01),
            rolling_window_trades=online_config.get("rollingWindowTrades", 50),
            min_weight=online_config.get("minWeight", 0.0),
            max_weight=online_config.get("maxWeight", 2.0)
        )
        
        self.enabled = online_config.get("enabled", False)
        self.last_update_time: Optional[datetime] = None
        self.update_interval_trades = online_config.get("updateIntervalTrades", 10)
        
        logger.info(f"OnlineLearningManager initialized: enabled={self.enabled}")
    
    def update_weights_from_recent_trades(self) -> Optional[Dict[str, float]]:
        """
        Update strategy weights based on recent trades
        
        Returns:
            Updated weights dict or None if not enough trades
        """
        if not self.enabled:
            return None
        
        try:
            # Get recent closed trades
            all_trades = self.data_collector.get_all_trades()
            closed_trades = [t for t in all_trades if t.get("exit_time") is not None]
            
            if len(closed_trades) < self.update_interval_trades:
                return None
            
            # Update weights
            updated_weights = self.weight_optimizer.update_from_trades(closed_trades)
            self.last_update_time = datetime.utcnow()
            
            logger.info(f"Updated strategy weights from {len(closed_trades)} trades")
            logger.debug(f"New weights: {updated_weights}")
            
            return updated_weights
            
        except Exception as e:
            logger.error(f"Error updating weights: {e}", exc_info=True)
            return None
    
    def should_update(self) -> bool:
        """Check if weights should be updated"""
        if not self.enabled:
            return False
        
        try:
            all_trades = self.data_collector.get_all_trades()
            closed_trades = [t for t in all_trades if t.get("exit_time") is not None]
            
            # Update if we have enough new trades since last update
            if self.last_update_time is None:
                return len(closed_trades) >= self.update_interval_trades
            
            # Count trades since last update
            recent_trades = [
                t for t in closed_trades
                if t.get("exit_time") and datetime.fromisoformat(t["exit_time"]) > self.last_update_time
            ]
            
            return len(recent_trades) >= self.update_interval_trades
            
        except Exception as e:
            logger.error(f"Error checking update condition: {e}", exc_info=True)
            return False
    
    def get_current_weights(self) -> Dict[str, float]:
        """Get current strategy weights"""
        return self.weight_optimizer.get_weights()
    
    def get_performance_stats(self) -> Dict[str, Dict[str, float]]:
        """Get performance statistics for all strategies"""
        return self.weight_optimizer.get_all_performance_stats()

