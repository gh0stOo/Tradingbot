"""Retry Handler with Exponential Backoff and Bybit-specific Error Mapping"""

import time
import logging
from typing import Callable, Any, Optional, Type
from utils.exceptions import (
    APIError, BybitAPIError, RateLimitError, TradingBotError
)

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior"""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True
    ):
        """
        Initialize retry configuration

        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay between retries
            backoff_factor: Exponential backoff multiplier
            jitter: Add random jitter to avoid thundering herd
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = self.initial_delay * (self.backoff_factor ** attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            import random
            delay = delay * (0.5 + random.random())

        return delay


class BybitErrorMapper:
    """Map Bybit-specific error codes to appropriate exceptions"""

    # Bybit error codes that should trigger retry
    RETRYABLE_ERRORS = {
        '20001',  # Service unavailable
        '20002',  # Service busy
        '20003',  # Service timeout
        '10001',  # Failed to create order
        '10002',  # Operation failed
        '10003',  # Service unavailable
        '10004',  # Invalid request
        '10005',  # Too many requests
        '10006',  # Invalid signature
        '10007',  # Parameter error
        '10008',  # Order not found
        '10009',  # Cancel failed
        '10010',  # Query failed
    }

    # Rate limit error codes
    RATE_LIMIT_ERRORS = {
        '10005',  # Too many requests
    }

    @staticmethod
    def is_retryable(error_code: Optional[str]) -> bool:
        """
        Check if error is retryable

        Args:
            error_code: Bybit error code

        Returns:
            True if error should be retried
        """
        if error_code is None:
            return False
        return error_code in BybitErrorMapper.RETRYABLE_ERRORS

    @staticmethod
    def is_rate_limit(error_code: Optional[str]) -> bool:
        """
        Check if error is rate limit

        Args:
            error_code: Bybit error code

        Returns:
            True if error is rate limit
        """
        if error_code is None:
            return False
        return error_code in BybitErrorMapper.RATE_LIMIT_ERRORS

    @staticmethod
    def map_error(status_code: int, error_code: Optional[str], message: str, response_data: dict = None) -> APIError:
        """
        Map Bybit error to appropriate exception

        Args:
            status_code: HTTP status code
            error_code: Bybit error code
            message: Error message
            response_data: Response data

        Returns:
            Appropriate exception instance
        """
        # Check for rate limit first
        if status_code == 429 or BybitErrorMapper.is_rate_limit(error_code):
            retry_after = None
            if response_data and 'Retry-After' in response_data:
                retry_after = int(response_data['Retry-After'])
            return RateLimitError(message, retry_after=retry_after)

        # Check for other retryable errors
        if BybitErrorMapper.is_retryable(error_code):
            return BybitAPIError(message, status_code=status_code, error_code=error_code, response_data=response_data)

        # Non-retryable Bybit API error
        return BybitAPIError(message, status_code=status_code, error_code=error_code, response_data=response_data)


class RetryHandler:
    """Handles API calls with automatic retry and exponential backoff"""

    def __init__(self, config: RetryConfig = None):
        """
        Initialize retry handler

        Args:
            config: Retry configuration (uses defaults if not provided)
        """
        self.config = config or RetryConfig()

    def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with automatic retry on failure

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Function result

        Raises:
            APIError: If max retries exceeded or error is not retryable
            TradingBotError: Other trading bot errors
        """
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return func(*args, **kwargs)

            except RateLimitError as e:
                # Special handling for rate limits
                last_exception = e

                if attempt < self.config.max_retries:
                    delay = e.retry_after or self.config.get_delay(attempt)
                    logger.warning(
                        f"Rate limit hit, retrying in {delay:.1f}s (attempt {attempt + 1}/{self.config.max_retries + 1})"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Max retries exceeded for rate limit error: {e}")
                    raise

            except BybitAPIError as e:
                # Check if error is retryable
                last_exception = e

                if BybitErrorMapper.is_retryable(e.error_code) and attempt < self.config.max_retries:
                    delay = self.config.get_delay(attempt)
                    logger.warning(
                        f"Retryable Bybit error ({e.error_code}): {e}, "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.config.max_retries + 1})"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Non-retryable API error or max retries exceeded: {e}")
                    raise

            except APIError as e:
                # Generic API error - check status code for retry eligibility
                last_exception = e

                # Retry on server errors (5xx) and some client errors
                retryable_status_codes = {408, 429, 500, 502, 503, 504}

                if e.status_code in retryable_status_codes and attempt < self.config.max_retries:
                    delay = self.config.get_delay(attempt)
                    logger.warning(
                        f"Retryable API error (HTTP {e.status_code}): {e}, "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.config.max_retries + 1})"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Non-retryable API error or max retries exceeded: {e}")
                    raise

            except Exception as e:
                # Other exceptions - only retry for specific types
                last_exception = e

                # Retry on connection errors
                retryable_errors = (ConnectionError, TimeoutError, OSError)

                if isinstance(e, retryable_errors) and attempt < self.config.max_retries:
                    delay = self.config.get_delay(attempt)
                    logger.warning(
                        f"Connection error: {type(e).__name__}, "
                        f"retrying in {delay:.1f}s (attempt {attempt + 1}/{self.config.max_retries + 1})"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Non-retryable error or max retries exceeded: {e}")
                    raise

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception

    @staticmethod
    def create_bybit_handler(max_retries: int = 3) -> 'RetryHandler':
        """
        Create retry handler optimized for Bybit API

        Args:
            max_retries: Maximum retry attempts

        Returns:
            RetryHandler instance configured for Bybit
        """
        config = RetryConfig(
            max_retries=max_retries,
            initial_delay=0.5,  # Shorter initial delay for Bybit
            max_delay=30.0,     # Shorter max delay
            backoff_factor=2.0,
            jitter=True
        )
        return RetryHandler(config)
