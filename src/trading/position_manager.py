"""Position Management System - Exit Management and Monitoring"""

import time
import threading
from typing import Dict, Optional, List, Any, Callable
from datetime import datetime
import logging

from data.position_tracker import PositionTracker
from integrations.bybit import BybitClient

logger = logging.getLogger(__name__)


class PositionManager:
    """Manages position exits, monitoring, and auto-close logic"""
    
    def __init__(
        self,
        position_tracker: PositionTracker,
        bybit_client: Optional[BybitClient] = None,
        check_interval: float = 5.0,  # Check every 5 seconds
        auto_close_enabled: bool = True
    ):
        """
        Initialize Position Manager
        
        Args:
            position_tracker: PositionTracker instance
            bybit_client: BybitClient instance (for fetching current prices)
            check_interval: Interval in seconds between position checks
            auto_close_enabled: Enable automatic position closing
        """
        self.position_tracker = position_tracker
        self.bybit_client = bybit_client
        self.check_interval = check_interval
        self.auto_close_enabled = auto_close_enabled
        
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Multi-target tracking (TP1, TP2, TP3, TP4)
        self.multi_targets: Dict[int, Dict[str, float]] = {}  # trade_id -> {tp1: price, tp2: price, ...}
    
    def set_multi_targets(
        self,
        trade_id: int,
        targets: Dict[str, float]
    ) -> None:
        """
        Set multi-target exit prices for a position
        
        Args:
            trade_id: Trade ID
            targets: Dictionary with TP keys (tp1, tp2, tp3, tp4) and prices
        """
        self.multi_targets[trade_id] = targets
        logger.debug(f"Set multi-targets for trade {trade_id}: {targets}")
    
    def check_exit_conditions(
        self,
        trade_id: int,
        current_price: float
    ) -> Optional[str]:
        """
        Check if exit conditions are met (TP/SL)
        
        Args:
            trade_id: Trade ID
            current_price: Current market price
            
        Returns:
            Exit reason string if condition met, None otherwise
        """
        position = self.position_tracker.get_position(trade_id)
        if not position or position.get("status") != "open":
            return None
        
        side = position["side"]
        stop_loss = position.get("stop_loss")
        take_profit = position.get("take_profit")
        
        # Check stop loss
        if stop_loss:
            if side == "Buy" and current_price <= stop_loss:
                return "Stop Loss"
            elif side == "Sell" and current_price >= stop_loss:
                return "Stop Loss"
        
        # Check take profit (single TP)
        if take_profit:
            if side == "Buy" and current_price >= take_profit:
                return "Take Profit"
            elif side == "Sell" and current_price <= take_profit:
                return "Take Profit"
        
        # Check multi-targets (partial exits)
        if trade_id in self.multi_targets:
            targets = self.multi_targets[trade_id]
            for tp_key, tp_price in sorted(targets.items()):
                # Check if we've already hit this target (could track partial fills)
                # For now, check all targets and return the first one hit
                if side == "Buy" and current_price >= tp_price:
                    return f"Take Profit ({tp_key.upper()})"
                elif side == "Sell" and current_price <= tp_price:
                    return f"Take Profit ({tp_key.upper()})"
        
        return None
    
    def auto_close_position(
        self,
        trade_id: int,
        exit_reason: str,
        current_price: float
    ) -> bool:
        """
        Automatically close a position
        
        Args:
            trade_id: Trade ID
            exit_reason: Reason for exit
            current_price: Current market price
            
        Returns:
            True if successful
        """
        if not self.auto_close_enabled:
            logger.debug(f"Auto-close disabled, not closing position {trade_id}")
            return False
        
        logger.info(f"Auto-closing position {trade_id} at {current_price} ({exit_reason})")
        
        result = self.position_tracker.close_position(
            trade_id=trade_id,
            exit_price=current_price,
            exit_reason=exit_reason
        )
        
        if result:
            # Clean up multi-targets
            if trade_id in self.multi_targets:
                del self.multi_targets[trade_id]
            return True
        
        return False
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current market price for symbol
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current price or None
        """
        if not self.bybit_client:
            logger.warning("BybitClient not available for price lookup")
            return None
        
        try:
            tickers = self.bybit_client.get_tickers(category="linear")
            for ticker in tickers:
                if ticker.get("symbol") == symbol:
                    return float(ticker.get("lastPrice", 0))
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
        
        return None
    
    def calculate_unrealized_pnl(
        self,
        trade_id: int,
        current_price: Optional[float] = None
    ) -> Optional[float]:
        """
        Calculate unrealized PnL for open position
        
        Args:
            trade_id: Trade ID
            current_price: Current market price (fetched if not provided)
            
        Returns:
            Unrealized PnL or None
        """
        position = self.position_tracker.get_position(trade_id)
        if not position or position.get("status") != "open":
            return None
        
        if current_price is None:
            current_price = self.get_current_price(position["symbol"])
            if current_price is None:
                return None
        
        side = position["side"]
        quantity = position["quantity"]
        entry_price = position["entry_price"]
        
        if side == "Buy":
            unrealized_pnl = (current_price - entry_price) * quantity
        else:  # Sell
            unrealized_pnl = (entry_price - current_price) * quantity
        
        return unrealized_pnl
    
    def monitor_positions(self) -> None:
        """
        Monitor all open positions and check exit conditions
        This runs in a separate thread
        """
        logger.info("Position monitoring started")
        
        while not self.stop_event.is_set():
            try:
                open_positions = self.position_tracker.get_open_positions()
                
                if not open_positions:
                    # No open positions, wait longer
                    time.sleep(self.check_interval * 2)
                    continue
                
                # Check each position
                for trade_id, position in open_positions.items():
                    symbol = position["symbol"]
                    current_price = self.get_current_price(symbol)
                    
                    if current_price is None:
                        logger.debug(f"Could not fetch price for {symbol}, skipping check")
                        continue
                    
                    # Check exit conditions
                    exit_reason = self.check_exit_conditions(trade_id, current_price)
                    
                    if exit_reason:
                        # Auto-close if enabled
                        self.auto_close_position(trade_id, exit_reason, current_price)
                    
                    # Update unrealized PnL (could store this in position data)
                    unrealized_pnl = self.calculate_unrealized_pnl(trade_id, current_price)
                    if unrealized_pnl is not None:
                        logger.debug(
                            f"Position {trade_id} ({symbol}): "
                            f"Unrealized PnL = {unrealized_pnl:.2f}"
                        )
                
                # Wait before next check
                self.stop_event.wait(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in position monitoring loop: {e}", exc_info=True)
                time.sleep(self.check_interval)
        
        logger.info("Position monitoring stopped")
    
    def start_monitoring(self) -> bool:
        """
        Start position monitoring in background thread
        
        Returns:
            True if started successfully
        """
        if self.monitoring_active:
            logger.warning("Position monitoring already active")
            return False
        
        if not self.bybit_client:
            logger.warning("Cannot start monitoring without BybitClient")
            return False
        
        self.stop_event.clear()
        self.monitoring_active = True
        
        self.monitoring_thread = threading.Thread(
            target=self.monitor_positions,
            daemon=True,
            name="PositionMonitor"
        )
        self.monitoring_thread.start()
        
        logger.info("Position monitoring thread started")
        return True
    
    def stop_monitoring(self) -> None:
        """Stop position monitoring"""
        if not self.monitoring_active:
            return
        
        self.stop_event.set()
        self.monitoring_active = False
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=10.0)
        
        logger.info("Position monitoring stopped")
    
    def get_position_summary(self) -> Dict[str, Any]:
        """
        Get summary of all open positions with unrealized PnL
        
        Returns:
            Dictionary with position summaries
        """
        open_positions = self.position_tracker.get_open_positions()
        summary = {
            "total_open": len(open_positions),
            "positions": [],
            "total_unrealized_pnl": 0.0
        }
        
        for trade_id, position in open_positions.items():
            current_price = self.get_current_price(position["symbol"])
            unrealized_pnl = self.calculate_unrealized_pnl(trade_id, current_price)
            
            pos_summary = {
                "trade_id": trade_id,
                "symbol": position["symbol"],
                "side": position["side"],
                "entry_price": position["entry_price"],
                "current_price": current_price,
                "quantity": position["quantity"],
                "stop_loss": position.get("stop_loss"),
                "take_profit": position.get("take_profit"),
                "unrealized_pnl": unrealized_pnl,
                "entry_time": position.get("entry_time")
            }
            
            summary["positions"].append(pos_summary)
            
            if unrealized_pnl is not None:
                summary["total_unrealized_pnl"] += unrealized_pnl
        
        return summary

