"""Unit Tests for Strategies (Isolated)"""

import unittest
from decimal import Decimal
from events.market_event import MarketEvent
from strategies.volatility_expansion import VolatilityExpansionStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.trend_continuation import TrendContinuationStrategy


class TestStrategiesIsolated(unittest.TestCase):
    """Test strategies in isolation"""
    
    def setUp(self) -> None:
        """Set up test fixtures"""
        self.config = {
            "volatilityExpansion": {
                "enabled": True,
                "compressionLookback": 20,
                "expansionThreshold": 1.5,
                "rMultipleTarget": 2.5,
                "minConfidence": 0.65,
            },
            "meanReversion": {
                "enabled": True,
                "fastMoveThreshold": 0.03,
                "volumeClimaxRatio": 2.0,
                "maxHoldMinutes": 60,
                "minConfidence": 0.60,
            },
            "trendContinuation": {
                "enabled": True,
                "pullbackThreshold": 0.015,
                "volatilityResetRatio": 0.60,
                "minConfidence": 0.70,
            },
        }
        
        self.volatility_strategy = VolatilityExpansionStrategy(self.config)
        self.mean_reversion_strategy = MeanReversionStrategy(self.config)
        self.trend_strategy = TrendContinuationStrategy(self.config)
    
    def test_volatility_strategy_enabled(self) -> None:
        """Test volatility expansion strategy is enabled"""
        self.assertTrue(self.volatility_strategy.is_enabled())
        self.assertEqual(self.volatility_strategy.name, "volatility_expansion")
    
    def test_mean_reversion_strategy_enabled(self) -> None:
        """Test mean reversion strategy is enabled"""
        self.assertTrue(self.mean_reversion_strategy.is_enabled())
        self.assertEqual(self.mean_reversion_strategy.name, "mean_reversion")
    
    def test_trend_strategy_enabled(self) -> None:
        """Test trend continuation strategy is enabled"""
        self.assertTrue(self.trend_strategy.is_enabled())
        self.assertEqual(self.trend_strategy.name, "trend_continuation")
    
    def test_strategy_generate_signals_empty_without_data(self) -> None:
        """Test strategies return empty list without market data"""
        market_event = MarketEvent(
            symbol="BTCUSDT",
            price=Decimal("50000"),
            volume=Decimal("1000"),
            source="Test",
        )
        
        # Without additional_data (klines), strategies should return empty
        signals = self.volatility_strategy.generate_signals(market_event)
        self.assertEqual(len(signals), 0)
        
        signals = self.mean_reversion_strategy.generate_signals(market_event)
        self.assertEqual(len(signals), 0)
        
        signals = self.trend_strategy.generate_signals(market_event)
        self.assertEqual(len(signals), 0)
    
    def test_strategy_disabled(self) -> None:
        """Test strategy can be disabled"""
        config_disabled = self.config.copy()
        config_disabled["volatilityExpansion"]["enabled"] = False
        
        strategy = VolatilityExpansionStrategy(config_disabled)
        self.assertFalse(strategy.is_enabled())
        
        market_event = MarketEvent(
            symbol="BTCUSDT",
            price=Decimal("50000"),
            volume=Decimal("1000"),
            source="Test",
        )
        
        signals = strategy.generate_signals(market_event)
        self.assertEqual(len(signals), 0)  # Should return empty when disabled


if __name__ == "__main__":
    unittest.main()

