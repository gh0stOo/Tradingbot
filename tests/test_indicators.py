"""Tests for Technical Indicators"""

import unittest
import pandas as pd
import numpy as np

from src.trading.indicators import Indicators


class TestIndicators(unittest.TestCase):
    """Test technical indicators calculation"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.indicators = Indicators(enable_cache=False)
    
    def create_test_data(self, length: int = 100) -> pd.DataFrame:
        """Create test OHLCV data"""
        dates = pd.date_range(start='2024-01-01', periods=length, freq='1min')
        base_price = 100.0
        returns = np.random.randn(length) * 0.01
        prices = base_price * (1 + returns).cumprod()
        
        return pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': prices * (1 + np.abs(np.random.randn(length) * 0.01)),
            'low': prices * (1 - np.abs(np.random.randn(length) * 0.01)),
            'close': prices,
            'volume': np.random.rand(length) * 1000
        })
    
    def test_ema_calculation(self):
        """Test EMA calculation"""
        df = self.create_test_data(50)
        close = df['close']
        ema = self.indicators.ema(close, 20)
        
        self.assertEqual(len(ema), len(close))
        self.assertFalse(ema.isna().all())
        # EMA should be close to price
        self.assertAlmostEqual(ema.iloc[-1], close.iloc[-1], delta=close.iloc[-1] * 0.1)
    
    def test_sma_calculation(self):
        """Test SMA calculation"""
        df = self.create_test_data(50)
        close = df['close']
        sma = self.indicators.sma(close, 20)
        
        self.assertEqual(len(sma), len(close))
        # SMA should be close to mean of last 20 prices
        self.assertAlmostEqual(sma.iloc[-1], close.iloc[-20:].mean(), delta=0.1)
    
    def test_rsi_calculation(self):
        """Test RSI calculation"""
        df = self.create_test_data(50)
        close = df['close']
        rsi = self.indicators.rsi(close, 14)
        
        self.assertEqual(len(rsi), len(close))
        # RSI should be between 0 and 100
        self.assertGreaterEqual(rsi.iloc[-1], 0)
        self.assertLessEqual(rsi.iloc[-1], 100)
    
    def test_atr_calculation(self):
        """Test ATR calculation"""
        df = self.create_test_data(50)
        atr = self.indicators.atr(df['high'], df['low'], df['close'], 14)
        
        self.assertEqual(len(atr), len(df))
        self.assertFalse(atr.isna().all())
        # ATR should be positive
        self.assertGreater(atr.iloc[-1], 0)
    
    def test_macd_calculation(self):
        """Test MACD calculation"""
        df = self.create_test_data(50)
        close = df['close']
        macd_data = self.indicators.macd(close, 12, 26, 9)
        
        self.assertIn("macd", macd_data)
        self.assertIn("signal", macd_data)
        self.assertIn("histogram", macd_data)
        self.assertEqual(len(macd_data["macd"]), len(close))
    
    def test_bollinger_bands_calculation(self):
        """Test Bollinger Bands calculation"""
        df = self.create_test_data(50)
        close = df['close']
        bb = self.indicators.bollinger_bands(close, 20, 2)
        
        self.assertIn("upper", bb)
        self.assertIn("middle", bb)
        self.assertIn("lower", bb)
        # Upper should be > middle > lower
        self.assertGreater(bb["upper"].iloc[-1], bb["middle"].iloc[-1])
        self.assertGreater(bb["middle"].iloc[-1], bb["lower"].iloc[-1])
    
    def test_calculate_all(self):
        """Test calculate_all method"""
        df = self.create_test_data(100)  # Need enough data
        
        result = self.indicators.calculate_all(df)
        
        self.assertIsInstance(result, dict)
        self.assertIn("ema8", result)
        self.assertIn("rsi", result)
        self.assertIn("atr", result)
        self.assertIn("macd", result)
        self.assertIn("currentPrice", result)
        
        # Check values are reasonable
        self.assertGreater(result["currentPrice"], 0)
        self.assertGreaterEqual(result["rsi"], 0)
        self.assertLessEqual(result["rsi"], 100)


if __name__ == '__main__':
    unittest.main()
