"""Parameter Scheduler for Genetic Algorithm Optimization"""

import time
import threading
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta

from ml.genetic_optimizer import GeneticAlgorithmOptimizer
from ml.backtest_runner import BacktestRunner

logger = logging.getLogger(__name__)


class ParameterScheduler:
    """
    Schedules periodic genetic algorithm optimization cycles.
    
    Runs GA optimization daily/weekly to continuously improve parameters.
    """
    
    def __init__(
        self,
        optimizer: GeneticAlgorithmOptimizer,
        backtest_runner: BacktestRunner,
        base_config: Dict[str, Any],
        schedule_type: str = "daily",  # "daily", "weekly", "manual"
        optimization_hour: int = 2,  # Hour of day to run optimization (UTC)
        optimization_day: int = 0,  # Day of week (0=Monday) for weekly schedule
        enabled: bool = True
    ):
        """
        Initialize Parameter Scheduler
        
        Args:
            optimizer: GeneticAlgorithmOptimizer instance
            backtest_runner: BacktestRunner instance
            base_config: Base trading bot configuration
            schedule_type: "daily", "weekly", or "manual"
            optimization_hour: Hour of day to run optimization (0-23, UTC)
            optimization_day: Day of week for weekly schedule (0=Monday, 6=Sunday)
            enabled: Enable automatic scheduling
        """
        self.optimizer = optimizer
        self.backtest_runner = backtest_runner
        self.base_config = base_config
        self.schedule_type = schedule_type
        self.optimization_hour = optimization_hour
        self.optimization_day = optimization_day
        self.enabled = enabled
        
        self.running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.last_optimization: Optional[datetime] = None
        self.optimization_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        
        logger.info(f"ParameterScheduler initialized: schedule={schedule_type}, hour={optimization_hour}, enabled={enabled}")
    
    def set_optimization_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Set callback function to be called after optimization completes
        
        Args:
            callback: Function that takes optimized parameters dict as argument
        """
        self.optimization_callback = callback
    
    def _should_run_optimization(self) -> bool:
        """Check if optimization should run based on schedule"""
        if not self.enabled:
            return False
        
        now = datetime.utcnow()
        
        if self.schedule_type == "daily":
            # Run if it's the optimization hour and we haven't run today
            if now.hour == self.optimization_hour:
                if self.last_optimization is None:
                    return True
                if self.last_optimization.date() < now.date():
                    return True
        
        elif self.schedule_type == "weekly":
            # Run if it's the optimization day and hour
            if now.weekday() == self.optimization_day and now.hour == self.optimization_hour:
                if self.last_optimization is None:
                    return True
                # Check if a week has passed
                if (now - self.last_optimization).days >= 7:
                    return True
        
        elif self.schedule_type == "manual":
            return False  # Manual scheduling only
        
        return False
    
    def _run_optimization(self) -> Optional[Dict[str, Any]]:
        """
        Run a single optimization cycle
        
        Returns:
            Optimized parameters dict or None if failed
        """
        try:
            logger.info("Starting scheduled parameter optimization...")
            
            # Create fitness function
            fitness_function = self.backtest_runner.create_fitness_function(self.base_config)
            
            # Run GA optimization
            best_individual = self.optimizer.evolve(
                fitness_function=fitness_function,
                max_generations=30,  # Reduced for scheduled runs
                min_fitness_improvement=0.001,
                stagnation_generations=5
            )
            
            optimized_params = best_individual.genes
            
            self.last_optimization = datetime.utcnow()
            
            logger.info(f"Optimization complete. Best fitness: {best_individual.fitness:.4f}")
            
            # Call callback if set
            if self.optimization_callback:
                try:
                    self.optimization_callback(optimized_params)
                except Exception as e:
                    logger.error(f"Error in optimization callback: {e}", exc_info=True)
            
            return optimized_params
            
        except Exception as e:
            logger.error(f"Error during optimization: {e}", exc_info=True)
            return None
    
    def _scheduler_loop(self) -> None:
        """Background loop for checking schedule and running optimizations"""
        logger.info("Parameter scheduler loop started")
        
        while self.running:
            try:
                if self._should_run_optimization():
                    self._run_optimization()
                
                # Check every minute
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                time.sleep(60)
        
        logger.info("Parameter scheduler loop stopped")
    
    def start(self) -> None:
        """Start the scheduler in background thread"""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        if not self.enabled:
            logger.info("Scheduler is disabled")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        logger.info("Parameter scheduler started")
    
    def stop(self) -> None:
        """Stop the scheduler"""
        if not self.running:
            return
        
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=10.0)
            if self.scheduler_thread.is_alive():
                logger.warning("Scheduler thread did not terminate gracefully")
        
        logger.info("Parameter scheduler stopped")
    
    def run_now(self) -> Optional[Dict[str, Any]]:
        """
        Manually trigger optimization now (ignores schedule)
        
        Returns:
            Optimized parameters dict or None if failed
        """
        logger.info("Manual optimization triggered")
        return self._run_optimization()
    
    def get_last_optimization_time(self) -> Optional[datetime]:
        """Get timestamp of last optimization"""
        return self.last_optimization
    
    def get_next_optimization_time(self) -> Optional[datetime]:
        """Calculate next scheduled optimization time"""
        if not self.enabled or self.schedule_type == "manual":
            return None
        
        now = datetime.utcnow()
        
        if self.schedule_type == "daily":
            next_time = now.replace(hour=self.optimization_hour, minute=0, second=0, microsecond=0)
            if next_time <= now:
                next_time += timedelta(days=1)
            return next_time
        
        elif self.schedule_type == "weekly":
            days_until = (self.optimization_day - now.weekday()) % 7
            if days_until == 0 and now.hour >= self.optimization_hour:
                days_until = 7
            next_time = now.replace(hour=self.optimization_hour, minute=0, second=0, microsecond=0)
            next_time += timedelta(days=days_until)
            return next_time
        
        return None

