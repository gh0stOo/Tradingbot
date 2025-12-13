"""Bybit API Wrapper"""

import time
import hmac
import hashlib
import requests
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from utils.exceptions import BybitAPIError, APIError, RateLimitError
from utils.retry import retry_with_backoff
from integrations.rate_limiter import RateLimiter, RateLimitConfig

logger = logging.getLogger(__name__)

class BybitClient:
    """Bybit API v5 Client"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        """
        Initialize Bybit client
        
        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            testnet: Use testnet (default: False)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api-testnet.bybit.com" if testnet else "https://api.bybit.com"
        self.session = requests.Session()
        
        # Use Token Bucket rate limiter
        custom_limits = {
            "orders": RateLimitConfig(max_tokens=50, refill_rate=0.83, window_seconds=60),  # 50/min
            "market_data": RateLimitConfig(max_tokens=120, refill_rate=2.0, window_seconds=60),  # 120/min
        }
        self.rate_limiter = RateLimiter(custom_limits=custom_limits)
        
        # Legacy counter (kept for backwards compatibility)
        self.rate_limit_counter = 0
        self.last_request_time = time.time()
    
    def _generate_signature(self, timestamp: str, recv_window: str, params: str) -> str:
        """Generate HMAC-SHA256 signature"""
        param_str = f"{timestamp}{self.api_key}{recv_window}{params}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            param_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _rate_limit_check(self, endpoint: str = "") -> None:
        """
        Check and enforce rate limits using Token Bucket
        
        Args:
            endpoint: API endpoint path (optional, for endpoint-specific limiting)
        """
        # Use Token Bucket rate limiter
        if endpoint:
            self.rate_limiter.wait_if_needed(endpoint)
        else:
            # Fallback to legacy method if no endpoint provided
            current_time = time.time()
            if current_time - self.last_request_time > 60:
                self.rate_limit_counter = 0
                self.last_request_time = current_time
            
            if self.rate_limit_counter >= 100:  # Safety limit
                wait_time = 60 - (current_time - self.last_request_time)
                if wait_time > 0:
                    time.sleep(wait_time)
                    self.rate_limit_counter = 0
                    self.last_request_time = time.time()
            
            self.rate_limit_counter += 1
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, max_delay=30.0)
    def _public_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make public API request"""
        # Use Token Bucket rate limiter
        self._rate_limit_check(endpoint)
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.get(url, params=params or {}, timeout=30)
            
            # Check for rate limit
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError("Rate limit exceeded", retry_after=retry_after)
            
            response.raise_for_status()
            result = response.json()
            
            # Check Bybit API error codes
            if result.get("retCode") != 0:
                error_msg = result.get("retMsg", "Unknown error")
                error_code = result.get("retCode")
                raise BybitAPIError(
                    f"Bybit API error: {error_msg}",
                    status_code=response.status_code,
                    error_code=str(error_code),
                    response_data=result
                )
            
            return result
            
        except requests.exceptions.Timeout as e:
            raise APIError(f"Request timeout for {endpoint}: {e}", status_code=408)
        except requests.exceptions.ConnectionError as e:
            raise APIError(f"Connection error for {endpoint}: {e}", status_code=0)
        except requests.exceptions.HTTPError as e:
            raise APIError(f"HTTP error for {endpoint}: {e}", status_code=response.status_code)
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, max_delay=30.0)
    def _authenticated_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None,
        body: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated API request"""
        if not self.api_key or not self.api_secret:
            raise BybitAPIError("API key and secret required for authenticated requests", error_code="AUTH_REQUIRED")
        
        # Use Token Bucket rate limiter
        self._rate_limit_check(endpoint)
        
        timestamp = str(int(time.time() * 1000))
        recv_window = "5000"
        
        # Prepare parameters
        if method == "GET":
            param_str = "&".join([f"{k}={v}" for k, v in sorted((params or {}).items())])
        else:
            import json
            param_str = json.dumps(body or {})
        
        # Generate signature
        signature = self._generate_signature(timestamp, recv_window, param_str)
        
        # Prepare headers
        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-SIGN": signature,
            "X-BAPI-RECV-WINDOW": recv_window,
            "Content-Type": "application/json"
        }
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method == "GET":
                response = self.session.get(url, headers=headers, params=params or {}, timeout=30)
            else:
                response = self.session.post(url, headers=headers, json=body or {}, timeout=30)
            
            # Check for rate limit
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError("Rate limit exceeded", retry_after=retry_after)
            
            response.raise_for_status()
            result = response.json()
            
            # Check Bybit API error codes
            if result.get("retCode") != 0:
                error_msg = result.get("retMsg", "Unknown error")
                error_code = result.get("retCode")
                raise BybitAPIError(
                    f"Bybit API error: {error_msg}",
                    status_code=response.status_code,
                    error_code=str(error_code),
                    response_data=result
                )
            
            return result
            
        except requests.exceptions.Timeout as e:
            raise APIError(f"Request timeout for {endpoint}: {e}", status_code=408)
        except requests.exceptions.ConnectionError as e:
            raise APIError(f"Connection error for {endpoint}: {e}", status_code=0)
        except requests.exceptions.HTTPError as e:
            raise APIError(f"HTTP error for {endpoint}: {e}", status_code=response.status_code)
    
    def get_tickers(self, category: str = "linear") -> List[Dict[str, Any]]:
        """Get all tickers for category"""
        endpoint = "/v5/market/tickers"
        params = {"category": category}
        response = self._public_request(endpoint, params)
        return response.get("result", {}).get("list", [])
    
    def get_instruments_info(self, category: str = "linear", limit: int = 1000) -> List[Dict[str, Any]]:
        """Get instruments info"""
        endpoint = "/v5/market/instruments-info"
        params = {"category": category, "limit": limit}
        response = self._public_request(endpoint, params)
        return response.get("result", {}).get("list", [])
    
    def get_klines(
        self, 
        symbol: str, 
        category: str = "linear",
        interval: int = 1,
        limit: int = 100
    ) -> List[List[Any]]:
        """Get klines/candlestick data"""
        endpoint = "/v5/market/kline"
        params = {
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        response = self._public_request(endpoint, params)
        return response.get("result", {}).get("list", [])
    
    def get_funding_rate(self, symbol: str, category: str = "linear", limit: int = 10) -> List[Dict[str, Any]]:
        """Get funding rate history"""
        endpoint = "/v5/market/funding/history"
        params = {
            "category": category,
            "symbol": symbol,
            "limit": limit
        }
        response = self._public_request(endpoint, params)
        return response.get("result", {}).get("list", [])
    
    def get_open_interest(
        self, 
        symbol: str, 
        category: str = "linear",
        interval_time: str = "5min",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get open interest"""
        endpoint = "/v5/market/open-interest"
        params = {
            "category": category,
            "symbol": symbol,
            "intervalTime": interval_time,
            "limit": limit
        }
        response = self._public_request(endpoint, params)
        return response.get("result", {}).get("list", [])
    
    def get_wallet_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """Get wallet balance (requires authentication)"""
        endpoint = "/v5/account/wallet-balance"
        params = {"accountType": account_type}
        response = self._authenticated_request("GET", endpoint, params=params)
        return response.get("result", {})
    
    def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create order (requires authentication)"""
        endpoint = "/v5/order/create"
        response = self._authenticated_request("POST", endpoint, body=order_data)
        return response.get("result", {})

