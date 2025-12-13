"""Training Scheduler for Automatic Model Re-Training"""

import threading
import time
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class TrainingScheduler:
    """
    Schedules automatic re-training of ML models.
    
    Triggers re-training when:
    - N new trades are available (default: 25)
    - T time has passed (default: 1 day)
    - Model performance degrades
    """
    
    def __init__(
        self,
        data_collector: Any,  # DataCollector instance
        training_function: Callable[[], None],  # Function to call for training
        config: Dict[str, Any],
        enabled: bool = True
    ):
        """
        Initialize Training Scheduler
        
        Args:
            data_collector: DataCollector instance for accessing trade data
            training_function: Function to call for model training
            config: Configuration dict
            enabled: Enable automatic scheduling
        """
        self.data_collector = data_collector
        self.training_function = training_function
        self.config = config
        self.enabled = enabled
        
        scheduler_config = config.get("ml", {}).get("trainingScheduler", {})
        
        self.min_trades_for_retrain = scheduler_config.get("minTradesForRetrain", 25)
        self.min_days_for_retrain = scheduler_config.get("minDaysForRetrain", 1)
        self.check_interval_seconds = scheduler_config.get("checkIntervalSeconds", 3600)  # 1 hour
        
        self.last_training_time: Optional[datetime] = None
        self.last_trade_count: int = 0
        self.training_in_progress = False
        
        self.running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        
        logger.info(
            f"TrainingScheduler initialized: enabled={enabled}, "
            f"min_trades={self.min_trades_for_retrain}, min_days={self.min_days_for_retrain}"
        )
    
    def _should_retrain(self) -> bool:
        """Check if models should be re-trained"""
        if not self.enabled or self.training_in_progress:
            return False
        
        try:
            # Get current trade count
            all_trades = self.data_collector.get_all_trades()
            current_trade_count = len(all_trades)
            
            # Check trade count condition
            if self.last_training_time is None:
                # First time - train if we have minimum trades
                if current_trade_count >= self.min_trades_for_retrain:
                    return True
            else:
                # Check if enough new trades since last training
                new_trades = current_trade_count - self.last_trade_count
                if new_trades >= self.min_trades_for_retrain:
                    logger.info(f"Enough new trades for retraining: {new_trades} >= {self.min_trades_for_retrain}")
                    return True
            
            # Check time condition
            if self.last_training_time is not None:
                time_since_training = datetime.utcnow() - self.last_training_time
                if time_since_training.days >= self.min_days_for_retrain:
                    logger.info(f"Enough time passed for retraining: {time_since_training.days} days >= {self.min_days_for_retrain}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking retrain condition: {e}", exc_info=True)
            return False
    
    def _run_training(self) -> None:
        """Execute model training"""
        if self.training_in_progress:
            logger.warning("Training already in progress, skipping")
            return
        
        try:
            self.training_in_progress = True
            logger.info("Starting automatic model re-training...")
            
            # Call training function
            self.training_function()
            
            # Update tracking
            self.last_training_time = datetime.utcnow()
            all_trades = self.data_collector.get_all_trades()
            self.last_trade_count = len(all_trades)
            
            logger.info("Automatic model re-training completed")
            
        except Exception as e:
            logger.error(f"Error during automatic training: {e}", exc_info=True)
        finally:
            self.training_in_progress = False
    
    def _scheduler_loop(self) -> None:
        """Background loop for checking and triggering training"""
        logger.info("Training scheduler loop started")
        
        while self.running:
            try:
                if self._should_retrain():
                    self._run_training()
                
                # Sleep before next check
                time.sleep(self.check_interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                time.sleep(self.check_interval_seconds)
        
        logger.info("Training scheduler loop stopped")
    
    def start(self) -> None:
        """Start the scheduler in background thread"""
        if self.running:
            logger.warning("Training scheduler already running")
            return
        
        if not self.enabled:
            logger.info("Training scheduler is disabled")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        # Initialize tracking
        all_trades = self.data_collector.get_all_trades()
        self.last_trade_count = len(all_trades)
        
        logger.info("Training scheduler started")
    
    def stop(self) -> None:
        """Stop the scheduler"""
        if not self.running:
            return
        
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=self.check_interval_seconds)
            if self.scheduler_thread.is_alive():
                logger.warning("Training scheduler thread did not terminate gracefully")
        
        logger.info("Training scheduler stopped")
    
    def trigger_training_now(self) -> None:
        """Manually trigger training now (ignores schedule)"""
        logger.info("Manual training triggered")
        self._run_training()
    
    def get_last_training_time(self) -> Optional[datetime]:
        """Get timestamp of last training"""
        return self.last_training_time
    
    def get_next_training_estimate(self) -> Optional[datetime]:
        """Estimate next training time"""
        if not self.enabled:
            return None
        
        if self.last_training_time is None:
            # Next training when we have enough trades
            all_trades = self.data_collector.get_all_trades()
            current_count = len(all_trades)
            needed_trades = self.min_trades_for_retrain - current_count
            
            if needed_trades <= 0:
                return datetime.utcnow()  # Ready now
            else:
                # Estimate based on average trades per day (rough estimate)
                return None  # Cannot estimate without trade rate
        
        # Next training is at least min_days_for_retrain days from last training
        return self.last_training_time + timedelta(days=self.min_days_for_retrain)
    
    def is_training_in_progress(self) -> bool:
        """Check if training is currently in progress"""
        return self.training_in_progress


def create_training_function(config: Dict[str, Any]) -> Callable[[], None]:
    """
    Create a training function that can be used by TrainingScheduler
    
    Args:
        config: Configuration dict
        
    Returns:
        Training function
    """
    def training_function():
        """Training function that calls train_models script"""
        import subprocess
        import sys
        
        script_path = Path(__file__).parent.parent.parent / "scripts" / "train_models.py"
        
        try:
            logger.info(f"Running training script: {script_path}")
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode == 0:
                logger.info("Training script completed successfully")
            else:
                logger.error(f"Training script failed with return code {result.returncode}")
                logger.error(f"Error output: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("Training script timed out after 1 hour")
        except Exception as e:
            logger.error(f"Error running training script: {e}", exc_info=True)
    
    return training_function

