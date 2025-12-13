"""Unit Tests for TradingState"""

import unittest
from decimal import Decimal
from datetime import datetime
from core.trading_state import TradingState, Position, Order


class TestTradingState(unittest.TestCase):
    """Test TradingState"""
    
    def setUp(self) -> None:
        """Set up test fixtures"""
        self.state = TradingState(initial_cash=Decimal("10000"))
    
    def test_initial_state(self) -> None:
        """Test initial state"""
        self.assertEqual(self.state.cash, Decimal("10000"))
        self.assertEqual(self.state.equity, Decimal("10000"))
        self.assertFalse(self.state.trading_enabled)
        self.assertEqual(len(self.state.get_open_positions()), 0)
    
    def test_add_position(self) -> None:
        """Test adding position"""
        success = self.state.add_position(
            symbol="BTCUSDT",
            side="Buy",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("51000"),
        )
        
        self.assertTrue(success)
        position = self.state.get_position("BTCUSDT")
        self.assertIsNotNone(position)
        self.assertEqual(position.symbol, "BTCUSDT")
        self.assertEqual(position.quantity, Decimal("0.1"))
    
    def test_duplicate_position(self) -> None:
        """Test duplicate position rejection"""
        self.state.add_position(
            symbol="BTCUSDT",
            side="Buy",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("51000"),
        )
        
        # Try to add same symbol again
        success = self.state.add_position(
            symbol="BTCUSDT",
            side="Buy",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("51000"),
        )
        
        self.assertFalse(success)
    
    def test_remove_position(self) -> None:
        """Test removing position"""
        self.state.add_position(
            symbol="BTCUSDT",
            side="Buy",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("51000"),
        )
        
        position = self.state.remove_position("BTCUSDT", Decimal("100"))
        self.assertIsNotNone(position)
        self.assertEqual(position.symbol, "BTCUSDT")
        
        # Position should be gone
        self.assertIsNone(self.state.get_position("BTCUSDT"))
    
    def test_cash_operations(self) -> None:
        """Test cash debit/credit"""
        # Debit
        success = self.state.debit_cash(Decimal("1000"))
        self.assertTrue(success)
        self.assertEqual(self.state.cash, Decimal("9000"))
        
        # Insufficient funds
        success = self.state.debit_cash(Decimal("10000"))
        self.assertFalse(success)
        self.assertEqual(self.state.cash, Decimal("9000"))
        
        # Credit
        self.state.credit_cash(Decimal("500"))
        self.assertEqual(self.state.cash, Decimal("9500"))
    
    def test_drawdown_calculation(self) -> None:
        """Test drawdown calculation"""
        # Increase equity to create peak
        self.state._equity = Decimal("15000")
        self.state._peak_equity = Decimal("15000")
        
        # Decrease equity
        self.state._equity = Decimal("12000")
        
        drawdown = self.state.drawdown
        drawdown_pct = self.state.drawdown_percent
        
        self.assertEqual(drawdown, Decimal("3000"))
        self.assertAlmostEqual(float(drawdown_pct), 20.0, places=1)
    
    def test_snapshot(self) -> None:
        """Test state snapshot"""
        self.state.enable_trading()
        self.state.add_position(
            symbol="BTCUSDT",
            side="Buy",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("51000"),
        )
        
        snapshot = self.state.snapshot()
        
        self.assertEqual(snapshot["cash"], 10000.0)
        self.assertEqual(snapshot["trading_enabled"], True)
        self.assertEqual(len(snapshot["open_positions"]), 1)


if __name__ == "__main__":
    unittest.main()

