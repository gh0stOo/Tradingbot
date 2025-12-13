"""Custom Exceptions for Trading Bot"""


class TradingBotError(Exception):
    """Base exception for all trading bot errors"""
    pass


class APIError(TradingBotError):
    """Exception for API-related errors"""
    
    def __init__(self, message: str, status_code: int = None, response_data: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class BybitAPIError(APIError):
    """Exception specifically for Bybit API errors"""
    
    def __init__(self, message: str, status_code: int = None, error_code: str = None, response_data: dict = None):
        super().__init__(message, status_code, response_data)
        self.error_code = error_code


class CalculationError(TradingBotError):
    """Exception for calculation errors (indicators, risk, etc.)"""
    pass


class ValidationError(TradingBotError):
    """Exception for validation errors (invalid parameters, missing data, etc.)"""
    pass


class DataError(TradingBotError):
    """Exception for data-related errors (missing data, invalid format, etc.)"""
    pass


class ConfigurationError(TradingBotError):
    """Exception for configuration errors"""
    pass


class OrderError(TradingBotError):
    """Exception for order execution errors"""
    
    def __init__(self, message: str, order_data: dict = None, error_code: str = None):
        super().__init__(message)
        self.order_data = order_data
        self.error_code = error_code


class RiskManagementError(TradingBotError):
    """Exception for risk management errors (circuit breaker, position limits, etc.)"""
    pass


class ModelError(TradingBotError):
    """Exception for ML model errors (loading, prediction, etc.)"""
    pass


class RateLimitError(APIError):
    """Exception for rate limit errors"""
    
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None):
        super().__init__(message)
        self.retry_after = retry_after  # Seconds to wait before retry

