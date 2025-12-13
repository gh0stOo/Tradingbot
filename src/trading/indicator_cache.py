"""Indicator Cache for Performance Optimization"""

import hashlib
import time
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging
import pandas as pd

logger = logging.getLogger(__name__)


class IndicatorCache:
    """Cache for indicator calculations to avoid redundant computation"""
    
    def __init__(self, cache_duration_seconds: int = 60):
        """
        Initialize Indicator Cache
        
        Args:
            cache_duration_seconds: How long to cache results (default: 60s for 1m klines)
        """
        self.cache_duration = cache_duration_seconds
        self.cache: Dict[str, Tuple[Any, float]] = {}  # key -> (value, timestamp)
        self.access_count = 0
        self.hit_count = 0
    
    def _generate_key(
        self,
        symbol: str,
        indicator_name: str,
        data_hash: str,
        params: Dict[str, Any]
    ) -> str:
        """
        Generate cache key from symbol, indicator, data hash, and parameters
        
        Args:
            symbol: Trading symbol
            indicator_name: Name of indicator
            data_hash: Hash of input data
            params: Indicator parameters
            
        Returns:
            Cache key string
        """
        param_str = "_".join(f"{k}={v}" for k, v in sorted(params.items()))
        key_str = f"{symbol}_{indicator_name}_{data_hash}_{param_str}"
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _hash_dataframe(self, df: pd.DataFrame) -> str:
        """
        Generate hash for DataFrame (first and last rows + length)
        
        Args:
            df: DataFrame to hash
            
        Returns:
            Hash string
        """
        if df.empty:
            return "empty"
        
        # Use first row, last row, and length for quick comparison
        first_row = df.iloc[0].to_dict()
        last_row = df.iloc[-1].to_dict()
        length = len(df)
        
        hash_str = f"{first_row}_{last_row}_{length}"
        return hashlib.md5(hash_str.encode()).hexdigest()
    
    def get(
        self,
        symbol: str,
        indicator_name: str,
        df: pd.DataFrame,
        params: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Get cached indicator value if available and fresh
        
        Args:
            symbol: Trading symbol
            indicator_name: Name of indicator
            df: Input DataFrame
            params: Indicator parameters
            
        Returns:
            Cached value or None if not cached or stale
        """
        self.access_count += 1
        
        data_hash = self._hash_dataframe(df)
        cache_key = self._generate_key(symbol, indicator_name, data_hash, params)
        
        if cache_key in self.cache:
            value, timestamp = self.cache[cache_key]
            age = time.time() - timestamp
            
            if age < self.cache_duration:
                self.hit_count += 1
                logger.debug(
                    f"Cache HIT for {symbol}/{indicator_name} "
                    f"(age: {age:.1f}s, hit_rate: {self.hit_rate:.1%})"
                )
                return value
            else:
                # Expired, remove from cache
                del self.cache[cache_key]
                logger.debug(f"Cache EXPIRED for {symbol}/{indicator_name}")
        
        return None
    
    def set(
        self,
        symbol: str,
        indicator_name: str,
        df: pd.DataFrame,
        params: Dict[str, Any],
        value: Any
    ) -> None:
        """
        Store indicator value in cache
        
        Args:
            symbol: Trading symbol
            indicator_name: Name of indicator
            df: Input DataFrame
            params: Indicator parameters
            value: Value to cache
        """
        data_hash = self._hash_dataframe(df)
        cache_key = self._generate_key(symbol, indicator_name, data_hash, params)
        
        self.cache[cache_key] = (value, time.time())
        logger.debug(f"Cached {symbol}/{indicator_name}")
        
        # Cleanup old entries periodically
        if len(self.cache) > 1000:
            self._cleanup_expired()
    
    def _cleanup_expired(self) -> None:
        """Remove expired cache entries"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if current_time - timestamp >= self.cache_duration
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def clear(self, symbol: Optional[str] = None) -> None:
        """
        Clear cache entries
        
        Args:
            symbol: If provided, only clear entries for this symbol
        """
        if symbol:
            keys_to_remove = [
                key for key in self.cache.keys()
                if key.startswith(hashlib.md5(symbol.encode()).hexdigest()[:8])
            ]
            for key in keys_to_remove:
                del self.cache[key]
            logger.info(f"Cleared cache for {symbol}")
        else:
            self.cache.clear()
            logger.info("Cleared entire cache")
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        return self.hit_count / self.access_count if self.access_count > 0 else 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "size": len(self.cache),
            "access_count": self.access_count,
            "hit_count": self.hit_count,
            "hit_rate": round(self.hit_rate * 100, 2),
            "cache_duration": self.cache_duration
        }


class IncrementalIndicatorCalculator:
    """Calculate indicators incrementally when possible"""
    
    def __init__(self):
        """Initialize incremental calculator"""
        self.previous_values: Dict[str, Any] = {}
    
    def incremental_ema(
        self,
        current_price: float,
        previous_ema: Optional[float],
        period: int,
        is_first: bool = False
    ) -> float:
        """
        Calculate EMA incrementally (only need previous EMA value)
        
        Args:
            current_price: Current price
            previous_ema: Previous EMA value
            period: EMA period
            is_first: Whether this is the first value
            
        Returns:
            New EMA value
        """
        if is_first or previous_ema is None:
            return current_price
        
        # EMA formula: EMA = Price(t) * k + EMA(t-1) * (1-k)
        # where k = 2 / (period + 1)
        k = 2.0 / (period + 1)
        return current_price * k + previous_ema * (1 - k)
    
    def incremental_sma(
        self,
        prices: list,
        period: int
    ) -> Optional[float]:
        """
        Calculate SMA incrementally from sliding window
        
        Args:
            prices: List of recent prices (should be length = period)
            period: SMA period
            
        Returns:
            SMA value or None if insufficient data
        """
        if len(prices) < period:
            return None
        
        return sum(prices[-period:]) / period
    
    def store_previous_value(self, key: str, value: Any) -> None:
        """Store previous calculated value for incremental calculation"""
        self.previous_values[key] = value
    
    def get_previous_value(self, key: str) -> Optional[Any]:
        """Get previous calculated value"""
        return self.previous_values.get(key)

