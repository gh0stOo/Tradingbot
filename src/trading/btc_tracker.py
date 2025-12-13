"""BTC Price Tracker for Crash Detection"""

import time
from typing import Dict, List, Optional
from collections import deque

class BTCTracker:
    """Track BTC prices for crash detection"""
    
    def __init__(self, history_hours: int = 24):
        """
        Initialize BTC Tracker
        
        Args:
            history_hours: Number of hours of price history to keep (default: 24)
        """
        self.history_hours = history_hours
        # Store (timestamp, price) tuples
        self.price_history: deque = deque(maxlen=1000)  # Store up to 1000 price points
    
    def update_price(self, price: float, timestamp: Optional[float] = None) -> None:
        """
        Update BTC price
        
        Args:
            price: Current BTC price
            timestamp: Unix timestamp (default: current time)
        """
        if timestamp is None:
            timestamp = time.time()
        
        self.price_history.append((timestamp, price))
    
    def get_price_change_24h(self, current_price: float) -> Optional[float]:
        """
        Calculate BTC price change over last 24 hours
        
        Args:
            current_price: Current BTC price
            
        Returns:
            Price change percentage (e.g., -0.03 for -3%) or None if insufficient history
        """
        if not self.price_history:
            return None
        
        # Find price from ~24 hours ago
        current_time = time.time()
        target_time = current_time - (24 * 3600)  # 24 hours ago
        
        # Find closest historical price
        historical_price = None
        for ts, price in self.price_history:
            if ts <= target_time:
                historical_price = price
            else:
                break
        
        # If no price old enough, use oldest available
        if historical_price is None and self.price_history:
            historical_price = self.price_history[0][1]
        
        if historical_price is None or historical_price == 0:
            return None
        
        # Calculate percentage change
        price_change = (current_price - historical_price) / historical_price
        return price_change
    
    def get_price_change_period(self, current_price: float, hours: float = 24) -> Optional[float]:
        """
        Calculate BTC price change over specified period
        
        Args:
            current_price: Current BTC price
            hours: Number of hours to look back
            
        Returns:
            Price change percentage or None if insufficient history
        """
        if not self.price_history:
            return None
        
        current_time = time.time()
        target_time = current_time - (hours * 3600)
        
        historical_price = None
        for ts, price in self.price_history:
            if ts <= target_time:
                historical_price = price
            else:
                break
        
        if historical_price is None and self.price_history:
            historical_price = self.price_history[0][1]
        
        if historical_price is None or historical_price == 0:
            return None
        
        price_change = (current_price - historical_price) / historical_price
        return price_change
    
    def clear_old_history(self, max_age_hours: int = 48) -> None:
        """
        Clear price history older than specified hours
        
        Args:
            max_age_hours: Maximum age in hours for price history
        """
        if not self.price_history:
            return
        
        current_time = time.time()
        cutoff_time = current_time - (max_age_hours * 3600)
        
        # Remove old entries
        while self.price_history and self.price_history[0][0] < cutoff_time:
            self.price_history.popleft()
