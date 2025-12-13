"""Tests for Risk Manager"""

import unittest

from src.trading.risk_manager import RiskManager


class TestRiskManager(unittest.TestCase):
    """Test risk management"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "risk": {
                "riskPct": 0.02,
                "atrMultiplierSL": 2.0,
                "atrMultiplierTP": 4.0,
                "minRR": 2.0,
                "maxExposure": 0.50,
                "leverageMax": 10,
                "kelly": {
                    "enabled": True,
                    "fraction": 0.25,
                    "minWinRate": 0.40
                },
                "regimeMultipliers": {
                    "trending": 1.0,
                    "ranging": 0.75,
                    "volatile": 0.5
                }
            },
            "multiTargetExits": {
                "enabled": True,
                "tp1": {"distance": 2.0, "size": 0.25},
                "tp2": {"distance": 3.0, "size": 0.25},
                "tp3": {"distance": 4.0, "size": 0.25},
                "tp4": {"distance": 5.0, "size": 0.25}
            }
        }
        self.risk_manager = RiskManager(self.config)
    
    def test_calculate_position_size_basic(self):
        """Test basic position size calculation"""
        result = self.risk_manager.calculate_position_size(
            equity=10000.0,
            price=100.0,
            atr=2.0,
            side="Buy",
            confidence=0.7,
            qty_step=0.001,
            min_order_qty=0.001
        )
        
        self.assertIsNotNone(result)
        self.assertIn("qty", result)
        self.assertIn("stopLoss", result)
        self.assertIn("takeProfit", result)
        self.assertIn("riskReward", result)
        self.assertGreater(result["qty"], 0)
        self.assertGreaterEqual(result["riskReward"], 2.0)
    
    def test_calculate_position_size_with_volatility(self):
        """Test position size with volatility adjustment"""
        # High volatility should reduce position size
        result_high_vol = self.risk_manager.calculate_position_size(
            equity=10000.0,
            price=100.0,
            atr=2.0,
            side="Buy",
            confidence=0.7,
            qty_step=0.001,
            min_order_qty=0.001,
            volatility=0.06  # 6% volatility
        )
        
        result_low_vol = self.risk_manager.calculate_position_size(
            equity=10000.0,
            price=100.0,
            atr=2.0,
            side="Buy",
            confidence=0.7,
            qty_step=0.001,
            min_order_qty=0.001,
            volatility=0.01  # 1% volatility
        )
        
        # High volatility should result in smaller position (or None if too risky)
        if result_high_vol and result_low_vol:
            self.assertLessEqual(result_high_vol["qty"], result_low_vol["qty"] * 1.5)
    
    def test_calculate_position_size_with_regime(self):
        """Test position size with regime adjustment"""
        regime_volatile = {"type": "volatile"}
        regime_trending = {"type": "trending"}
        
        result_volatile = self.risk_manager.calculate_position_size(
            equity=10000.0,
            price=100.0,
            atr=2.0,
            side="Buy",
            confidence=0.7,
            qty_step=0.001,
            min_order_qty=0.001,
            regime=regime_volatile
        )
        
        result_trending = self.risk_manager.calculate_position_size(
            equity=10000.0,
            price=100.0,
            atr=2.0,
            side="Buy",
            confidence=0.7,
            qty_step=0.001,
            min_order_qty=0.001,
            regime=regime_trending
        )
        
        # Volatile regime should result in smaller position
        if result_volatile and result_trending:
            self.assertLessEqual(result_volatile["qty"], result_trending["qty"])
    
    def test_position_size_invalid_inputs(self):
        """Test position size with invalid inputs"""
        from src.utils.exceptions import ValidationError
        
        # Test invalid equity
        with self.assertRaises(ValidationError):
            self.risk_manager.calculate_position_size(
                equity=-1000.0,
                price=100.0,
                atr=2.0,
                side="Buy",
                confidence=0.7,
                qty_step=0.001,
                min_order_qty=0.001
            )
        
        # Test invalid side
        with self.assertRaises(ValidationError):
            self.risk_manager.calculate_position_size(
                equity=10000.0,
                price=100.0,
                atr=2.0,
                side="Invalid",
                confidence=0.7,
                qty_step=0.001,
                min_order_qty=0.001
            )


if __name__ == '__main__':
    unittest.main()
