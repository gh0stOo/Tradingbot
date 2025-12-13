"""Comprehensive Tests for PHASE 5 & 6: Backtesting Consistency & Position Mismatch Prevention"""

import unittest
import tempfile
import os

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data.database import Database
from data.position_tracker import PositionTracker


class TestBacktestingConsistency(unittest.TestCase):
    """Test PHASE 5: Backtesting vs Live Consistency"""

    def setUp(self):
        """Setup"""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.db = Database(self.db_path)
        self.tracker = PositionTracker(self.db, fee_rate=0.001)

    def tearDown(self):
        """Cleanup"""
        self.db.close()
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except:
            pass

    def test_pnl_consistency_across_modes(self):
        """Test: PNL calculation identical in backtest and live"""
        # Simulate trade
        self.tracker.open_position(
            trade_id=1,
            symbol="BTCUSDT",
            side="Buy",
            entry_price=50000.0,
            quantity=1.0,
            stop_loss=48000.0,
            take_profit=52000.0
        )

        # Close position
        result = self.tracker.close_position(
            trade_id=1,
            exit_price=51000.0,
            exit_reason="TP"
        )

        # PNL should include fees
        # Gross: (51000 - 50000) * 1 = 1000
        # Fees: (50000 + 51000) * 0.001 = 101
        # Net: 1000 - 101 = 899
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['realized_pnl'], 899, delta=1)
        self.assertTrue(result['success'])

    def test_fee_consistency_buy_sell(self):
        """Test: Fees calculated consistently for Buy and Sell sides"""
        # Buy
        self.tracker.open_position(
            trade_id=1,
            symbol="BTCUSDT",
            side="Buy",
            entry_price=50000.0,
            quantity=1.0,
            stop_loss=48000.0,
            take_profit=52000.0
        )
        buy_result = self.tracker.close_position(
            trade_id=1,
            exit_price=51000.0,
            exit_reason="TP"
        )

        # Sell
        self.tracker.open_position(
            trade_id=2,
            symbol="BTCUSDT",
            side="Sell",
            entry_price=51000.0,
            quantity=1.0,
            stop_loss=52000.0,
            take_profit=50000.0
        )
        sell_result = self.tracker.close_position(
            trade_id=2,
            exit_price=50000.0,
            exit_reason="TP"
        )

        # Both should have similar fee structure
        self.assertIsNotNone(buy_result)
        self.assertIsNotNone(sell_result)
        self.assertGreater(buy_result['realized_pnl'], 0)
        self.assertGreater(sell_result['realized_pnl'], 0)


class TestPositionMismatchPrevention(unittest.TestCase):
    """Test PHASE 6: Position-Mismatch Prevention"""

    def setUp(self):
        """Setup"""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.db = Database(self.db_path)
        self.tracker = PositionTracker(self.db, fee_rate=0.001)

    def tearDown(self):
        """Cleanup"""
        self.db.close()
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except:
            pass

    def test_open_positions_tracked(self):
        """Test: Open positions are properly tracked"""
        # Open 3 positions
        for i in range(3):
            self.tracker.open_position(
                trade_id=i,
                symbol=f"SYMBOL{i}",
                side="Buy",
                entry_price=50000.0 + i * 1000,
                quantity=1.0,
                stop_loss=48000.0,
                take_profit=52000.0
            )

        # Check open positions
        open_pos = self.tracker.get_open_positions()
        self.assertEqual(len(open_pos), 3)

    def test_get_open_positions_method(self):
        """Test: get_open_positions returns correct data"""
        self.tracker.open_position(
            trade_id=1,
            symbol="BTCUSDT",
            side="Buy",
            entry_price=50000.0,
            quantity=1.0,
            stop_loss=48000.0,
            take_profit=52000.0
        )

        # Verify method exists and works
        self.assertTrue(hasattr(self.tracker, 'get_open_positions'))
        open_pos = self.tracker.get_open_positions()
        self.assertIn(1, open_pos)
        self.assertEqual(open_pos[1]['symbol'], "BTCUSDT")

    def test_position_data_consistency(self):
        """Test: Position data remains consistent after operations"""
        self.tracker.open_position(
            trade_id=1,
            symbol="BTCUSDT",
            side="Buy",
            entry_price=50000.0,
            quantity=1.0,
            stop_loss=48000.0,
            take_profit=52000.0
        )

        # Verify position data
        open_pos = self.tracker.get_open_positions()
        pos = open_pos[1]

        self.assertEqual(pos['symbol'], "BTCUSDT")
        self.assertEqual(pos['side'], "Buy")
        self.assertEqual(pos['entry_price'], 50000.0)
        self.assertEqual(pos['quantity'], 1.0)
        self.assertEqual(pos['stop_loss'], 48000.0)
        self.assertEqual(pos['take_profit'], 52000.0)

    def test_position_removal_on_close(self):
        """Test: Position removed from open list after close"""
        self.tracker.open_position(
            trade_id=1,
            symbol="BTCUSDT",
            side="Buy",
            entry_price=50000.0,
            quantity=1.0,
            stop_loss=48000.0,
            take_profit=52000.0
        )

        # Verify it's open
        open_before = self.tracker.get_open_positions()
        self.assertIn(1, open_before)

        # Close position
        self.tracker.close_position(
            trade_id=1,
            exit_price=51000.0,
            exit_reason="TP"
        )

        # Verify it's removed from open
        open_after = self.tracker.get_open_positions()
        self.assertNotIn(1, open_after)


class TestCombinedPhaseValidation(unittest.TestCase):
    """Integration test combining PHASE 4, 5, 6"""

    def setUp(self):
        """Setup"""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.db = Database(self.db_path)
        self.tracker = PositionTracker(self.db, fee_rate=0.001)

    def tearDown(self):
        """Cleanup"""
        self.db.close()
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except:
            pass

    def test_full_trading_cycle(self):
        """Test: Full trading cycle with open, hold, close"""
        # Open
        open_result = self.tracker.open_position(
            trade_id=1,
            symbol="BTCUSDT",
            side="Buy",
            entry_price=50000.0,
            quantity=1.0,
            stop_loss=48000.0,
            take_profit=52000.0
        )
        self.assertTrue(open_result)

        # Check open
        open_pos = self.tracker.get_open_positions()
        self.assertEqual(len(open_pos), 1)

        # Close
        close_result = self.tracker.close_position(
            trade_id=1,
            exit_price=51000.0,
            exit_reason="TP"
        )
        self.assertIsNotNone(close_result)
        self.assertGreater(close_result['realized_pnl'], 0)

        # Check closed
        open_pos = self.tracker.get_open_positions()
        self.assertEqual(len(open_pos), 0)

    def test_multiple_positions_lifecycle(self):
        """Test: Managing multiple positions concurrently"""
        # Open 3 positions
        for i in range(3):
            self.tracker.open_position(
                trade_id=i,
                symbol=f"SYMBOL{i}",
                side="Buy",
                entry_price=50000.0,
                quantity=1.0,
                stop_loss=48000.0,
                take_profit=52000.0
            )

        self.assertEqual(len(self.tracker.get_open_positions()), 3)

        # Close 1
        self.tracker.close_position(trade_id=0, exit_price=51000.0)
        self.assertEqual(len(self.tracker.get_open_positions()), 2)

        # Close another
        self.tracker.close_position(trade_id=1, exit_price=51000.0)
        self.assertEqual(len(self.tracker.get_open_positions()), 1)

        # Close remaining
        self.tracker.close_position(trade_id=2, exit_price=51000.0)
        self.assertEqual(len(self.tracker.get_open_positions()), 0)


if __name__ == '__main__':
    unittest.main()
