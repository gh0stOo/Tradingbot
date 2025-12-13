"""Tests for Trading Strategies"""

import unittest
import pandas as pd
import numpy as np
from typing import Dict, Any

from src.trading.strategies import Strategies
from src.trading.regime_detector import RegimeDetector


class TestStrategies(unittest.TestCase):
    """Test trading strategies"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "strategies": {
                "emaTrend": {"weight": 1.0},
                "macdTrend": {"weight": 1.0},
                "rsiMeanReversion": {"weight": 1.0},
                "bollingerMeanReversion": {"weight": 1.0},
                "adxTrend": {"weight": 1.0},
                "volumeProfile": {"weight": 1.0},
                "volatilityBreakout": {"weight": 1.0},
                "multiTimeframe": {"weight": 1.0}
            }
        }
        self.strategies = Strategies(self.config)
        self.regime_detector = RegimeDetector()
    
    def create_test_indicators(self, regime_type: str = "trending") -> Dict[str, float]:
        """Create test indicator dictionary"""
        indicators = {
            "ema8": 100.0,
            "ema21": 99.0,
            "ema50": 98.0,
            "ema200": 97.0,
            "rsi": 50.0,
            "atr": 2.0,
            "macd": 0.5,
            "macdSignal": 0.3,
            "macdHist": 0.2,
            "bbUpper": 105.0,
            "bbLower": 95.0,
            "bbMiddle": 100.0,
            "vwap": 100.0,
            "stochastic": 50.0,
            "adx": 30.0,
            "volatility": 0.02,
            "currentPrice": 101.0
        }
        
        if regime_type == "trending":
            indicators["adx"] = 30.0
            indicators["ema8"] = 102.0
            indicators["ema21"] = 101.0
        elif regime_type == "ranging":
            indicators["adx"] = 15.0
            indicators["rsi"] = 45.0
        elif regime_type == "volatile":
            indicators["adx"] = 20.0
            indicators["volatility"] = 0.05
        
        return indicators
    
    def create_test_klines(self, length: int = 100) -> pd.DataFrame:
        """Create test kline DataFrame"""
        dates = pd.date_range(start='2024-01-01', periods=length, freq='1min')
        prices = 100 + np.cumsum(np.random.randn(length) * 0.5)
        
        return pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': prices + np.random.rand(length) * 2,
            'low': prices - np.random.rand(length) * 2,
            'close': prices,
            'volume': np.random.rand(length) * 1000
        })
    
    def test_ema_trend_strategy_trending(self):
        """Test EMA trend strategy in trending market"""
        indicators = self.create_test_indicators("trending")
        regime = self.regime_detector.detect_regime(
            indicators["adx"],
            indicators["atr"],
            indicators["currentPrice"]
        )
        
        result = self.strategies.ema_trend(indicators, regime, indicators["currentPrice"])
        
        if result:
            self.assertIn("side", result)
            self.assertIn("confidence", result)
            self.assertIn(result["side"], ["Buy", "Sell"])
            self.assertGreaterEqual(result["confidence"], 0.0)
            self.assertLessEqual(result["confidence"], 1.0)
    
    def test_macd_trend_strategy(self):
        """Test MACD trend strategy"""
        indicators = self.create_test_indicators("trending")
        regime = self.regime_detector.detect_regime(
            indicators["adx"],
            indicators["atr"],
            indicators["currentPrice"]
        )
        
        result = self.strategies.macd_trend(indicators, regime, indicators["currentPrice"])
        
        if result:
            self.assertIn("side", result)
            self.assertIn("confidence", result)
    
    def test_rsi_mean_reversion_strategy(self):
        """Test RSI mean reversion strategy"""
        indicators = self.create_test_indicators("ranging")
        # Set RSI to extreme values
        indicators["rsi"] = 25.0  # Oversold
        
        regime = self.regime_detector.detect_regime(
            indicators["adx"],
            indicators["atr"],
            indicators["currentPrice"]
        )
        
        result = self.strategies.rsi_mean_reversion(indicators, regime, indicators["currentPrice"])
        
        if result:
            self.assertIn("side", result)
            # Oversold should suggest Buy
            if indicators["rsi"] < 30:
                self.assertEqual(result["side"], "Buy")
    
    def test_bollinger_mean_reversion_strategy(self):
        """Test Bollinger mean reversion strategy"""
        indicators = self.create_test_indicators("ranging")
        # Price near lower band
        indicators["currentPrice"] = 96.0  # Near bbLower (95.0)
        
        regime = self.regime_detector.detect_regime(
            indicators["adx"],
            indicators["atr"],
            indicators["currentPrice"]
        )
        
        result = self.strategies.bollinger_mean_reversion(indicators, regime, indicators["currentPrice"])
        
        if result:
            self.assertIn("side", result)
    
    def test_run_all_strategies(self):
        """Test running all strategies"""
        indicators = self.create_test_indicators("trending")
        regime = self.regime_detector.detect_regime(
            indicators["adx"],
            indicators["atr"],
            indicators["currentPrice"]
        )
        klines = self.create_test_klines()
        
        signals = self.strategies.run_all_strategies(
            indicators=indicators,
            regime=regime,
            price=indicators["currentPrice"],
            klines=klines,
            klines_m5=klines,
            klines_m15=klines
        )
        
        self.assertIsInstance(signals, list)
        # Should have some signals (may be empty if conditions not met)
        for signal in signals:
            if signal:
                self.assertIn("strategy", signal)
                self.assertIn("side", signal)
                self.assertIn("confidence", signal)


if __name__ == '__main__':
    unittest.main()
