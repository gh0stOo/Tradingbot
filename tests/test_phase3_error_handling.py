"""Unit Tests for PHASE 3: API Error Handling"""

import unittest
import time
from unittest.mock import Mock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.retry_handler import RetryHandler, RetryConfig, BybitErrorMapper
from utils.exceptions import RateLimitError, BybitAPIError, APIError


class TestRetryConfig(unittest.TestCase):
    """Test RetryConfig functionality"""

    def test_retry_config_defaults(self):
        """Test: RetryConfig uses correct defaults"""
        config = RetryConfig()

        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.initial_delay, 1.0)
        self.assertEqual(config.max_delay, 60.0)
        self.assertEqual(config.backoff_factor, 2.0)
        self.assertTrue(config.jitter)

    def test_exponential_backoff_calculation(self):
        """Test: Exponential backoff calculated correctly"""
        config = RetryConfig(initial_delay=1.0, backoff_factor=2.0, jitter=False)

        delay0 = config.get_delay(0)  # 1 * 2^0 = 1
        delay1 = config.get_delay(1)  # 1 * 2^1 = 2
        delay2 = config.get_delay(2)  # 1 * 2^2 = 4

        self.assertEqual(delay0, 1.0)
        self.assertEqual(delay1, 2.0)
        self.assertEqual(delay2, 4.0)

    def test_max_delay_capped(self):
        """Test: Delay capped at max_delay"""
        config = RetryConfig(initial_delay=1.0, max_delay=10.0, backoff_factor=10.0, jitter=False)

        delay = config.get_delay(5)  # Would be 10^5 without cap

        self.assertEqual(delay, 10.0)


class TestBybitErrorMapper(unittest.TestCase):
    """Test Bybit error mapping"""

    def test_retryable_error_detection(self):
        """Test: Retryable errors correctly identified"""
        self.assertTrue(BybitErrorMapper.is_retryable('20001'))  # Service unavailable
        self.assertTrue(BybitErrorMapper.is_retryable('10005'))  # Too many requests
        self.assertFalse(BybitErrorMapper.is_retryable('40001'))  # Invalid parameter
        self.assertFalse(BybitErrorMapper.is_retryable(None))

    def test_rate_limit_detection(self):
        """Test: Rate limit errors correctly identified"""
        self.assertTrue(BybitErrorMapper.is_rate_limit('10005'))
        self.assertFalse(BybitErrorMapper.is_rate_limit('20001'))
        self.assertFalse(BybitErrorMapper.is_rate_limit(None))

    def test_http_429_mapped_to_rate_limit(self):
        """Test: HTTP 429 mapped to RateLimitError"""
        error = BybitErrorMapper.map_error(429, '10005', 'Too many requests')

        self.assertIsInstance(error, RateLimitError)

    def test_retryable_bybit_error_mapping(self):
        """Test: Retryable Bybit errors mapped correctly"""
        error = BybitErrorMapper.map_error(500, '20001', 'Service unavailable')

        self.assertIsInstance(error, BybitAPIError)
        self.assertEqual(error.error_code, '20001')


class TestRetryHandler(unittest.TestCase):
    """Test RetryHandler functionality"""

    def setUp(self):
        """Setup retry handler"""
        self.config = RetryConfig(max_retries=2, initial_delay=0.01, jitter=False)
        self.handler = RetryHandler(self.config)

    def test_successful_execution_no_retry(self):
        """Test: Successful function execution doesn't retry"""
        mock_func = Mock(return_value='success')

        result = self.handler.execute_with_retry(mock_func)

        self.assertEqual(result, 'success')
        self.assertEqual(mock_func.call_count, 1)

    def test_retry_on_transient_error(self):
        """Test: Transient errors trigger retry"""
        mock_func = Mock(side_effect=[
            ConnectionError('Network error'),
            ConnectionError('Network error'),
            'success'
        ])

        result = self.handler.execute_with_retry(mock_func)

        self.assertEqual(result, 'success')
        self.assertEqual(mock_func.call_count, 3)

    def test_max_retries_exceeded(self):
        """Test: Max retries exceeded raises error"""
        mock_func = Mock(side_effect=ConnectionError('Network error'))

        with self.assertRaises(ConnectionError):
            self.handler.execute_with_retry(mock_func)

        # Should be called max_retries + 1 times
        self.assertEqual(mock_func.call_count, self.config.max_retries + 1)

    def test_non_retryable_error_raised_immediately(self):
        """Test: Non-retryable errors raised without retry"""
        mock_func = Mock(side_effect=ValueError('Invalid value'))

        with self.assertRaises(ValueError):
            self.handler.execute_with_retry(mock_func)

        # Should be called only once
        self.assertEqual(mock_func.call_count, 1)

    def test_rate_limit_error_with_retry_after(self):
        """Test: Rate limit error with Retry-After header"""
        rate_limit_error = RateLimitError('Rate limited', retry_after=1)
        mock_func = Mock(side_effect=[rate_limit_error, 'success'])

        result = self.handler.execute_with_retry(mock_func)

        self.assertEqual(result, 'success')
        self.assertEqual(mock_func.call_count, 2)

    def test_bybit_error_retryable(self):
        """Test: Retryable Bybit errors trigger retry"""
        bybit_error = BybitAPIError('Service busy', error_code='20001')
        mock_func = Mock(side_effect=[bybit_error, 'success'])

        result = self.handler.execute_with_retry(mock_func)

        self.assertEqual(result, 'success')
        self.assertEqual(mock_func.call_count, 2)

    def test_bybit_error_non_retryable(self):
        """Test: Non-retryable Bybit errors raised immediately"""
        bybit_error = BybitAPIError('Invalid parameter', error_code='40001')
        mock_func = Mock(side_effect=bybit_error)

        with self.assertRaises(BybitAPIError):
            self.handler.execute_with_retry(mock_func)

        # Should be called only once
        self.assertEqual(mock_func.call_count, 1)

    def test_bybit_handler_factory(self):
        """Test: Bybit handler factory creates optimized config"""
        handler = RetryHandler.create_bybit_handler(max_retries=3)

        self.assertEqual(handler.config.max_retries, 3)
        self.assertEqual(handler.config.initial_delay, 0.5)  # Optimized for Bybit
        self.assertEqual(handler.config.max_delay, 30.0)  # Shorter max delay


if __name__ == '__main__':
    unittest.main()
