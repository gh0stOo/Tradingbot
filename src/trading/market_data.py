"""Market Data Module - Bybit API Client"""

import logging
from typing import Dict, List, Optional, Any
from integrations.bybit import BybitClient

logger = logging.getLogger(__name__)

class MarketData:
    """Market Data handler for trading bot"""
    
    def __init__(self, bybit_client: BybitClient):
        """
        Initialize Market Data handler
        
        Args:
            bybit_client: BybitClient instance
        """
        self.client = bybit_client
    
    def get_top_coins(self, top_n: int = 50, min_volume: float = 5000000) -> List[Dict[str, Any]]:
        """
        Get top N coins by 24h volume
        
        Args:
            top_n: Number of top coins to return
            min_volume: Minimum 24h volume
            
        Returns:
            List of coin data dictionaries
        """
        if not self.client:
            # Return empty list if no client
            return []
        
        # Public endpoints don't require API key
        tickers = self.client.get_tickers()
        instruments = self.client.get_instruments_info()
        
        # Create instrument map
        instrument_map = {inst["symbol"]: inst for inst in instruments}
        
        # Filter and sort by volume
        filtered = []
        for ticker in tickers:
            symbol = ticker.get("symbol")
            if not symbol or symbol not in instrument_map:
                continue
            
            inst = instrument_map[symbol]
            if inst.get("status") != "Trading":
                continue
            
            volume24h = float(ticker.get("turnover24h", 0))
            if volume24h < min_volume:
                continue
            
            price = float(ticker.get("lastPrice", 0))
            if price <= 0:
                continue
            
            filtered.append({
                "symbol": symbol,
                "lastPrice": price,
                "volume24h": volume24h,
                "priceChangePercent": float(ticker.get("price24hPcnt", 0)) * 100,
                "high24h": float(ticker.get("highPrice24h", 0)),
                "low24h": float(ticker.get("lowPrice24h", 0)),
                "tickSize": inst.get("priceFilter", {}).get("tickSize", "0.01"),
                "qtyStep": inst.get("lotSizeFilter", {}).get("qtyStep", "0.001"),
                "minOrderQty": inst.get("lotSizeFilter", {}).get("minOrderQty", "0.001"),
                "maxOrderQty": inst.get("lotSizeFilter", {}).get("maxOrderQty", "1000")
            })
        
        # Sort by volume descending and return top N
        filtered.sort(key=lambda x: x["volume24h"], reverse=True)
        return filtered[:top_n]
    
    def get_btc_price(self) -> float:
        """Get BTCUSDT price"""
        if not self.client:
            return 50000.0  # Default fallback
        
        # Public endpoint doesn't require API key
        tickers = self.client.get_tickers()
        for ticker in tickers:
            if ticker.get("symbol") == "BTCUSDT":
                return float(ticker.get("lastPrice", 0))
        return 0.0
    
    def get_symbol_data(
        self, 
        symbol: str,
        intervals: List[int] = [1, 5, 15],
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get complete data for a symbol
        
        Args:
            symbol: Trading symbol
            intervals: List of interval minutes [1, 5, 15]
            limit: Number of candles to fetch
            
        Returns:
            Dictionary with klines, funding rate, and open interest
        """
        result = {
            "symbol": symbol,
            "klines": {},
            "fundingRate": [],
            "openInterest": []
        }
        
        if not self.client:
            return result
        
        # Get klines for each interval (public endpoint, no API key needed)
        for interval in intervals:
            klines = self.client.get_klines(symbol, interval=interval, limit=limit)
            result["klines"][f"m{interval}"] = klines
        
        # Get funding rate (public endpoint)
        try:
            result["fundingRate"] = self.client.get_funding_rate(symbol, limit=10)
        except Exception as e:
            logger.debug(f"Failed to get funding rate for {symbol}: {e}")
            result["fundingRate"] = []
        
        # Get open interest (public endpoint)
        try:
            result["openInterest"] = self.client.get_open_interest(symbol, limit=20)
        except Exception as e:
            logger.debug(f"Failed to get open interest for {symbol}: {e}")
            result["openInterest"] = []
        
        return result

