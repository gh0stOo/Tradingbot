"""Retry Logic with Exponential Backoff"""

import time
import random
import logging
from typing import Callable, Type, Tuple, Optional, Any
from functools import wraps

from utils.exceptions import APIError, RateLimitError, TradingBotError, ValidationError, ConfigurationError

logger = logging.getLogger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (APIError, RateLimitError),
    non_retryable_exceptions: Tuple[Type[Exception], ...] = (ValidationError, ConfigurationError)
):
    """
    Decorator for retrying function calls with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay in seconds between retries
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delay (helps avoid thundering herd)
        retryable_exceptions: Tuple of exceptions that should trigger a retry
        non_retryable_exceptions: Tuple of exceptions that should NOT be retried
        
    Returns:
        Decorated function with retry logic
    """
    from utils.exceptions import ValidationError, ConfigurationError
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                
                except non_retryable_exceptions as e:
                    # Don't retry these exceptions
                    logger.error(f"{func.__name__} failed with non-retryable exception: {e}")
                    raise
                
                except retryable_exceptions as e:
                    last_exception = e
                    
                    # Check if we have retries left
                    if attempt >= max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries. "
                            f"Last error: {e}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        initial_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    # Add jitter if enabled
                    if jitter:
                        jitter_amount = delay * 0.1 * random.random()
                        delay = delay + jitter_amount
                    
                    # Special handling for RateLimitError
                    if isinstance(e, RateLimitError) and e.retry_after:
                        delay = max(delay, e.retry_after)
                    
                    logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    
                    time.sleep(delay)
                
                except Exception as e:
                    # For unknown exceptions, log and re-raise immediately
                    logger.error(
                        f"{func.__name__} failed with unexpected exception: {type(e).__name__}: {e}",
                        exc_info=True
                    )
                    raise
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            
        return wrapper
    return decorator


class RetryHandler:
    """Class for handling retries with context-aware logic"""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0
    ):
        """
        Initialize Retry Handler
        
        Args:
            max_retries: Maximum number of retries
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
    
    def execute(
        self,
        func: Callable,
        *args,
        context: Optional[dict] = None,
        **kwargs
    ) -> Any:
        """
        Execute function with retry logic
        
        Args:
            func: Function to execute
            *args: Positional arguments for function
            context: Optional context dictionary for logging
            **kwargs: Keyword arguments for function
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries fail
        """
        context = context or {}
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            
            except (APIError, RateLimitError) as e:
                last_exception = e
                
                if attempt >= self.max_retries:
                    logger.error(
                        f"Function {func.__name__} failed after {self.max_retries} retries. "
                        f"Context: {context}, Last error: {e}",
                        exc_info=True
                    )
                    raise
                
                delay = min(
                    self.initial_delay * (2.0 ** attempt),
                    self.max_delay
                )
                
                if isinstance(e, RateLimitError) and e.retry_after:
                    delay = max(delay, e.retry_after)
                
                logger.warning(
                    f"Function {func.__name__} failed (attempt {attempt + 1}/{self.max_retries + 1}). "
                    f"Context: {context}, Error: {e}. Retrying in {delay:.2f}s..."
                )
                
                time.sleep(delay)
            
            except Exception as e:
                logger.error(
                    f"Function {func.__name__} failed with unexpected exception. "
                    f"Context: {context}, Error: {type(e).__name__}: {e}",
                    exc_info=True
                )
                raise
        
        if last_exception:
            raise last_exception

