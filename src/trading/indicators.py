"""Technical Indicators Module"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any

from trading.indicator_cache import IndicatorCache, IncrementalIndicatorCalculator

class Indicators:
    """Technical Indicators Calculator with caching and incremental updates"""
    
    def __init__(self, enable_cache: bool = True, cache_duration: int = 60):
        """
        Initialize Indicators Calculator
        
        Args:
            enable_cache: Enable indicator caching
            cache_duration: Cache duration in seconds (default: 60 for 1m klines)
        """
        self.enable_cache = enable_cache
        self.cache = IndicatorCache(cache_duration_seconds=cache_duration) if enable_cache else None
        self.incremental_calc = IncrementalIndicatorCalculator()
    
    @staticmethod
    def parse_klines(klines: List[List[Any]]) -> pd.DataFrame:
        """
        Parse Bybit kline data to DataFrame
        
        Args:
            klines: List of kline arrays from Bybit API
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        if not klines:
            return pd.DataFrame()
        
        data = []
        for k in klines:
            data.append({
                "timestamp": int(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5])
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values("timestamp").reset_index(drop=True)
        return df
    
    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average"""
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        """Simple Moving Average"""
        return data.rolling(window=period).mean()
    
    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """MACD Indicator"""
        ema_fast = Indicators.ema(data, fast)
        ema_slow = Indicators.ema(data, slow)
        macd_line = ema_fast - ema_slow
        signal_line = Indicators.ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }
    
    @staticmethod
    def bollinger_bands(data: pd.Series, period: int = 20, std_dev: int = 2) -> Dict[str, pd.Series]:
        """Bollinger Bands"""
        sma = Indicators.sma(data, period)
        std = data.rolling(window=period).std()
        
        return {
            "upper": sma + (std * std_dev),
            "middle": sma,
            "lower": sma - (std * std_dev)
        }
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Average True Range"""
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = Indicators.ema(tr, period)
        return atr
    
    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """Average Directional Index"""
        # Calculate True Range
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Calculate Directional Movement
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        # Smooth TR and DM
        atr_smooth = Indicators.ema(tr, period)
        plus_di = 100 * (Indicators.ema(plus_dm, period) / atr_smooth)
        minus_di = 100 * (Indicators.ema(minus_dm, period) / atr_smooth)
        
        # Calculate ADX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = Indicators.ema(dx, period)
        
        return adx.iloc[-1] if len(adx) > 0 else 0.0
    
    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Volume Weighted Average Price"""
        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        return vwap
    
    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Stochastic Oscillator"""
        lowest_low = low.rolling(window=period).min()
        highest_high = high.rolling(window=period).max()
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        return k_percent
    
    def calculate_all(self, df: pd.DataFrame, symbol: str = "") -> Dict[str, float]:
        """
        Calculate all indicators from DataFrame with caching
        
        Args:
            df: DataFrame with columns: open, high, low, close, volume
            symbol: Trading symbol (for caching)
            
        Returns:
            Dictionary with all indicator values
        """
        if df.empty or len(df) < 50:
            return {}
        
        # Try to get from cache if enabled
        if self.cache and symbol:
            cached_result = self.cache.get(symbol, "all_indicators", df, {})
            if cached_result is not None:
                return cached_result
        
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]
        
        # EMA
        ema8 = Indicators.ema(close, 8)
        ema21 = Indicators.ema(close, 21)
        ema50 = Indicators.ema(close, 50)
        ema200 = Indicators.ema(close, 200)
        
        # RSI
        rsi14 = Indicators.rsi(close, 14)
        
        # ATR
        atr14 = Indicators.atr(high, low, close, 14)
        
        # MACD
        macd_data = Indicators.macd(close, 12, 26, 9)
        
        # Bollinger Bands
        bb = Indicators.bollinger_bands(close, 20, 2)
        
        # VWAP
        vwap_data = Indicators.vwap(high, low, close, volume)
        
        # Stochastic
        stoch = Indicators.stochastic(high, low, close, 14)
        
        # ADX
        adx_value = Indicators.adx(high, low, close, 14)
        
        # Volatility (standard deviation of returns)
        returns = close.pct_change()
        volatility = returns.std() * np.sqrt(len(returns))
        
        # Get latest values
        return {
            "ema8": float(ema8.iloc[-1]) if len(ema8) > 0 else 0.0,
            "ema21": float(ema21.iloc[-1]) if len(ema21) > 0 else 0.0,
            "ema50": float(ema50.iloc[-1]) if len(ema50) > 0 else 0.0,
            "ema200": float(ema200.iloc[-1]) if len(ema200) > 0 else 0.0,
            "rsi": float(rsi14.iloc[-1]) if len(rsi14) > 0 else 50.0,
            "atr": float(atr14.iloc[-1]) if len(atr14) > 0 else 0.0,
            "macd": float(macd_data["macd"].iloc[-1]) if len(macd_data["macd"]) > 0 else 0.0,
            "macdSignal": float(macd_data["signal"].iloc[-1]) if len(macd_data["signal"]) > 0 else 0.0,
            "macdHist": float(macd_data["histogram"].iloc[-1]) if len(macd_data["histogram"]) > 0 else 0.0,
            "bbUpper": float(bb["upper"].iloc[-1]) if len(bb["upper"]) > 0 else 0.0,
            "bbLower": float(bb["lower"].iloc[-1]) if len(bb["lower"]) > 0 else 0.0,
            "bbMiddle": float(bb["middle"].iloc[-1]) if len(bb["middle"]) > 0 else 0.0,
            "vwap": float(vwap_data.iloc[-1]) if len(vwap_data) > 0 else 0.0,
            "stochastic": float(stoch.iloc[-1]) if len(stoch) > 0 else 50.0,
            "adx": adx_value,
            "volatility": float(volatility) if not np.isnan(volatility) else 0.0,
            "currentPrice": float(close.iloc[-1]) if len(close) > 0 else 0.0
        }
        
        # Cache result if enabled
        if self.cache and symbol:
            self.cache.set(symbol, "all_indicators", df, {}, result)
        
        return result

