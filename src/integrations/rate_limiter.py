"""Rate Limiting with Token Bucket Algorithm"""

import time
import threading
from typing import Optional, Dict, Any
from collections import defaultdict
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    max_tokens: int = 100  # Maximum tokens (requests) per window
    refill_rate: float = 100.0  # Tokens per second
    window_seconds: int = 60  # Time window in seconds
    burst_allowance: int = 10  # Allow bursts up to this many tokens over limit


class TokenBucket:
    """Token Bucket implementation for rate limiting"""
    
    def __init__(self, config: RateLimitConfig):
        """
        Initialize Token Bucket
        
        Args:
            config: RateLimitConfig instance
        """
        self.config = config
        self.tokens = config.max_tokens
        self.last_refill = time.time()
        self.lock = threading.Lock()
    
    def _refill(self, current_time: float) -> None:
        """Refill tokens based on time elapsed"""
        if current_time <= self.last_refill:
            return
        
        elapsed = current_time - self.last_refill
        tokens_to_add = elapsed * self.config.refill_rate
        
        # Cap at max_tokens + burst_allowance
        max_capacity = self.config.max_tokens + self.config.burst_allowance
        self.tokens = min(self.tokens + tokens_to_add, max_capacity)
        self.last_refill = current_time
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from the bucket
        
        Args:
            tokens: Number of tokens to consume (default: 1)
            
        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        with self.lock:
            current_time = time.time()
            self._refill(current_time)
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    def wait_time(self, tokens: int = 1) -> float:
        """
        Calculate wait time until tokens are available
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Seconds to wait (0 if available now)
        """
        with self.lock:
            current_time = time.time()
            self._refill(current_time)
            
            if self.tokens >= tokens:
                return 0.0
            
            tokens_needed = tokens - self.tokens
            return tokens_needed / self.config.refill_rate
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current bucket statistics"""
        with self.lock:
            current_time = time.time()
            self._refill(current_time)
            return {
                "tokens": self.tokens,
                "max_tokens": self.config.max_tokens,
                "refill_rate": self.config.refill_rate,
                "last_refill": self.last_refill
            }


class RateLimiter:
    """Rate limiter with endpoint-specific limits"""
    
    # Default rate limits for different endpoint types
    DEFAULT_LIMITS = {
        "public": RateLimitConfig(max_tokens=120, refill_rate=2.0, window_seconds=60),  # 120/min
        "market_data": RateLimitConfig(max_tokens=120, refill_rate=2.0, window_seconds=60),  # 120/min
        "orders": RateLimitConfig(max_tokens=50, refill_rate=0.83, window_seconds=60),  # 50/min
        "account": RateLimitConfig(max_tokens=120, refill_rate=2.0, window_seconds=60),  # 120/min
        "position": RateLimitConfig(max_tokens=120, refill_rate=2.0, window_seconds=60),  # 120/min
        "wallet": RateLimitConfig(max_tokens=120, refill_rate=2.0, window_seconds=60),  # 120/min
    }
    
    def __init__(self, custom_limits: Optional[Dict[str, RateLimitConfig]] = None):
        """
        Initialize Rate Limiter
        
        Args:
            custom_limits: Optional dictionary of endpoint_type -> RateLimitConfig
        """
        self.buckets: Dict[str, TokenBucket] = {}
        self.lock = threading.Lock()
        
        # Initialize with defaults
        limits = self.DEFAULT_LIMITS.copy()
        if custom_limits:
            limits.update(custom_limits)
        
        for endpoint_type, config in limits.items():
            self.buckets[endpoint_type] = TokenBucket(config)
    
    def _get_endpoint_type(self, endpoint: str) -> str:
        """
        Determine endpoint type from endpoint path
        
        Args:
            endpoint: API endpoint path (e.g., "/v5/market/tickers")
            
        Returns:
            Endpoint type string
        """
        endpoint_lower = endpoint.lower()
        
        # Order endpoints
        if "/order/" in endpoint_lower or "/position/" in endpoint_lower:
            return "orders"
        
        # Account/Wallet endpoints
        if "/account/" in endpoint_lower or "/wallet/" in endpoint_lower:
            return "account"
        
        # Market data endpoints
        if "/market/" in endpoint_lower:
            return "market_data"
        
        # Default to public for safety
        return "public"
    
    def can_proceed(self, endpoint: str, tokens: int = 1) -> bool:
        """
        Check if request can proceed without waiting
        
        Args:
            endpoint: API endpoint path
            tokens: Number of tokens to consume (default: 1)
            
        Returns:
            True if request can proceed, False if rate limited
        """
        endpoint_type = self._get_endpoint_type(endpoint)
        bucket = self.buckets.get(endpoint_type, self.buckets["public"])
        return bucket.consume(tokens)
    
    def wait_if_needed(self, endpoint: str, tokens: int = 1) -> None:
        """
        Wait if necessary before making request
        
        Args:
            endpoint: API endpoint path
            tokens: Number of tokens needed (default: 1)
        """
        endpoint_type = self._get_endpoint_type(endpoint)
        bucket = self.buckets.get(endpoint_type, self.buckets["public"])
        
        wait_time = bucket.wait_time(tokens)
        if wait_time > 0:
            logger.debug(f"Rate limit wait for {endpoint_type}: {wait_time:.2f}s")
            time.sleep(wait_time)
            bucket.consume(tokens)
        else:
            bucket.consume(tokens)
    
    def get_stats(self, endpoint_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get rate limit statistics
        
        Args:
            endpoint_type: Optional specific endpoint type, otherwise returns all
            
        Returns:
            Dictionary with statistics
        """
        if endpoint_type:
            bucket = self.buckets.get(endpoint_type)
            if bucket:
                return {endpoint_type: bucket.get_stats()}
            return {}
        
        return {
            ep_type: bucket.get_stats()
            for ep_type, bucket in self.buckets.items()
        }


class RequestQueue:
    """Queue system for requests with prioritization"""
    
    def __init__(self, rate_limiter: RateLimiter):
        """
        Initialize Request Queue
        
        Args:
            rate_limiter: RateLimiter instance
        """
        self.rate_limiter = rate_limiter
        self.queue: list = []
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
    
    def add_request(
        self,
        endpoint: str,
        func: callable,
        *args,
        priority: int = 0,
        **kwargs
    ) -> Any:
        """
        Add request to queue and wait for execution
        
        Args:
            endpoint: API endpoint path
            func: Function to execute
            *args: Function arguments
            priority: Request priority (higher = more important)
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        # Wait if needed
        self.rate_limiter.wait_if_needed(endpoint)
        
        # Execute function
        return func(*args, **kwargs)

