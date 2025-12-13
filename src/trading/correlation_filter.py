"""Correlation Filter Module - Prevent correlated positions"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

class CorrelationFilter:
    """Filter trades based on correlation between symbols"""
    
    def __init__(self, max_correlation: float = 0.70, lookback_days: int = 30):
        """
        Initialize Correlation Filter
        
        Args:
            max_correlation: Maximum allowed correlation (0.0-1.0)
            lookback_days: Number of days for correlation calculation
        """
        self.max_correlation = max_correlation
        self.lookback_days = lookback_days
        self.correlation_cache: Dict[Tuple[str, str], float] = {}
        self.cache_timestamp: Optional[datetime] = None
        self.cache_duration = timedelta(hours=1)  # Cache for 1 hour
    
    def calculate_correlation(
        self,
        prices1: pd.Series,
        prices2: pd.Series,
        min_periods: int = 20
    ) -> float:
        """
        Calculate correlation between two price series
        
        Args:
            prices1: First price series
            prices2: Second price series
            min_periods: Minimum periods for correlation calculation
            
        Returns:
            Correlation coefficient (-1.0 to 1.0)
        """
        if len(prices1) < min_periods or len(prices2) < min_periods:
            return 0.0
        
        # Calculate percentage returns
        returns1 = prices1.pct_change().dropna()
        returns2 = prices2.pct_change().dropna()
        
        # Align series
        common_index = returns1.index.intersection(returns2.index)
        if len(common_index) < min_periods:
            return 0.0
        
        aligned_returns1 = returns1.loc[common_index]
        aligned_returns2 = returns2.loc[common_index]
        
        # Calculate correlation
        correlation = aligned_returns1.corr(aligned_returns2)
        
        # Handle NaN
        if np.isnan(correlation):
            return 0.0
        
        return float(correlation)
    
    def get_symbol_correlation(
        self,
        symbol1: str,
        symbol2: str,
        price_history1: Optional[List[float]] = None,
        price_history2: Optional[List[float]] = None
    ) -> float:
        """
        Get correlation between two symbols
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            price_history1: Optional price history for symbol1
            price_history2: Optional price history for symbol2
            
        Returns:
            Correlation coefficient
        """
        # Check cache first
        cache_key = tuple(sorted([symbol1, symbol2]))
        if cache_key in self.correlation_cache:
            # Check if cache is still valid
            if self.cache_timestamp and datetime.now() - self.cache_timestamp < self.cache_duration:
                return self.correlation_cache[cache_key]
        
        # If price histories provided, calculate directly
        if price_history1 and price_history2:
            prices1 = pd.Series(price_history1)
            prices2 = pd.Series(price_history2)
            correlation = self.calculate_correlation(prices1, prices2)
            
            # Cache result
            self.correlation_cache[cache_key] = correlation
            self.cache_timestamp = datetime.now()
            
            return correlation
        
        # Otherwise return 0 (no data available)
        return 0.0
    
    def check_correlation_violation(
        self,
        new_symbol: str,
        existing_symbols: List[str],
        price_histories: Optional[Dict[str, List[float]]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if new symbol would violate correlation constraints
        
        Args:
            new_symbol: New symbol to check
            existing_symbols: List of existing position symbols
            price_histories: Optional dictionary of price histories by symbol
            
        Returns:
            Tuple of (is_violation, violating_symbol)
        """
        if not existing_symbols:
            return (False, None)
        
        for existing_symbol in existing_symbols:
            # Get price histories if available
            hist1 = price_histories.get(new_symbol) if price_histories else None
            hist2 = price_histories.get(existing_symbol) if price_histories else None
            
            correlation = self.get_symbol_correlation(
                new_symbol,
                existing_symbol,
                hist1,
                hist2
            )
            
            # Check if correlation exceeds threshold
            if abs(correlation) > self.max_correlation:
                return (True, existing_symbol)
        
        return (False, None)
    
    def filter_correlated_symbols(
        self,
        candidate_symbols: List[str],
        existing_symbols: List[str],
        max_positions: int,
        price_histories: Optional[Dict[str, List[float]]] = None
    ) -> List[str]:
        """
        Filter candidate symbols to avoid high correlation with existing positions
        
        Args:
            candidate_symbols: List of candidate symbols to trade
            existing_symbols: List of symbols with existing positions
            max_positions: Maximum number of positions allowed
            price_histories: Optional dictionary of price histories by symbol
            
        Returns:
            Filtered list of symbols that don't violate correlation constraints
        """
        if not existing_symbols:
            return candidate_symbols[:max_positions]
        
        filtered = []
        
        for candidate in candidate_symbols:
            # Check if we've reached max positions
            if len(existing_symbols) + len(filtered) >= max_positions:
                break
            
            # Check correlation with existing positions
            violation, violating_symbol = self.check_correlation_violation(
                candidate,
                existing_symbols + filtered,
                price_histories
            )
            
            if not violation:
                filtered.append(candidate)
        
        return filtered

