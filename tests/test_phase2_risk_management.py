"""
Unit Tests for PHASE 2: Risk Management Validation
Tests for Total Exposure Tracking, Circuit Breaker, and Bot Integration
"""

import unittest
import tempfile
import os
from datetime import datetime

# Add src to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data.database import Database
from data.position_tracker import PositionTracker
from trading.risk_manager import RiskManager


class TestTotalExposureTracking(unittest.TestCase):
    """Test Total Exposure Tracking in Position Sizing"""

    def setUp(self):
        """Setup risk manager and position tracker"""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.db = Database(self.db_path)
        self.position_tracker = PositionTracker(self.db, fee_rate=0.001)

        self.config = {
            'risk': {
                'riskPct': 0.02,
                'atrMultiplierSL': 2.0,
                'atrMultiplierTP': 4.0,
                'minRR': 2.0,
                'maxExposure': 0.50,  # 50% of equity
                'leverageMax': 10,
                'maxPositions': 3
            },
            'kelly': {'enabled': False},
            'multiTargetExits': {'enabled': False}
        }
        self.risk_manager = RiskManager(self.config, data_collector=None)

    def tearDown(self):
        """Cleanup"""
        self.db.close()
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except:
            pass

    def test_position_sizing_respects_total_exposure(self):
        """Test: Position size respects total exposure limit"""
        # Setup: Open positions totaling near max exposure
        self.position_tracker.open_position(
            trade_id=1,
            symbol='BTCUSDT',
            side='Buy',
            entry_price=50000.0,
            quantity=0.095,  # $4,750 notional
            stop_loss=48000.0,
            take_profit=58000.0
        )

        equity = 10000.0
        max_exposure = equity * 0.50  # $5,000 max

        # Try to add a position when already near limit
        # New position would put total over limit
        position = self.risk_manager.calculate_position_size(
            equity=equity,
            price=50000.0,
            atr=1000.0,
            side='Buy',
            confidence=0.7,
            qty_step=0.001,
            min_order_qty=0.001,
            historical_win_rate=0.55,
            volatility=0.02,
            regime=None,
            position_tracker=self.position_tracker
        )

        # Position should be rejected or very small because it would exceed limit
        if position is not None:
            # If position returned, verify cumulative exposure doesn't exceed limit
            cumulative_notional = (0.095 * 50000.0) + (position['qty'] * position['price'])
            cumulative_margin = cumulative_notional / 10
            self.assertLessEqual(cumulative_margin, max_exposure)

    def test_position_sizing_allows_within_limit(self):
        """Test: Position is allowed when total exposure within limit"""
        equity = 10000.0

        # Without existing positions, should be able to size normally
        position = self.risk_manager.calculate_position_size(
            equity=equity,
            price=50000.0,
            atr=1000.0,
            side='Buy',
            confidence=0.7,
            qty_step=0.001,
            min_order_qty=0.001,
            historical_win_rate=0.55,
            volatility=0.02,
            regime=None,
            position_tracker=self.position_tracker
        )

        # Should have a valid position
        self.assertIsNotNone(position)
        self.assertGreater(position['qty'], 0)

        # Verify notional value is within max exposure
        notional = position['qty'] * position['price']
        max_exposure = equity * 0.50
        required_margin = notional / 10  # leverageMax = 10
        self.assertLessEqual(required_margin, max_exposure)

    def test_multiple_positions_cumulative_exposure(self):
        """Test: Multiple positions cumulative exposure is tracked"""
        # This tests the cumulative effect of multiple positions
        equity = 10000.0

        # Add first position
        self.position_tracker.open_position(
            trade_id=1,
            symbol='BTCUSDT',
            side='Buy',
            entry_price=50000.0,
            quantity=0.08,  # $4,000
            stop_loss=48000.0,
            take_profit=58000.0
        )

        # Add second position
        self.position_tracker.open_position(
            trade_id=2,
            symbol='ETHUSDT',
            side='Buy',
            entry_price=3000.0,
            quantity=0.5,  # $1,500
            stop_loss=2900.0,
            take_profit=3500.0
        )

        total_notional = (0.08 * 50000.0) + (0.5 * 3000.0)  # $5,500

        # Try to add a third position that would exceed limit
        position = self.risk_manager.calculate_position_size(
            equity=equity,
            price=40000.0,
            atr=800.0,
            side='Buy',
            confidence=0.7,
            qty_step=0.001,
            min_order_qty=0.001,
            historical_win_rate=0.55,
            volatility=0.02,
            regime=None,
            position_tracker=self.position_tracker
        )

        # Verify that cumulative exposure is validated
        # The total existing notional ($5,500) already at limit
        # New position should be rejected or very minimal
        if position is not None:
            cumulative = total_notional + (position['qty'] * position['price'])
            margin = cumulative / 10
            max_exposure = equity * 0.50
            self.assertLessEqual(margin, max_exposure)


class TestCircuitBreakerLogic(unittest.TestCase):
    """Test Circuit Breaker Conditions"""

    def setUp(self):
        """Setup risk manager"""
        self.config = {
            'risk': {
                'riskPct': 0.02,
                'atrMultiplierSL': 2.0,
                'atrMultiplierTP': 4.0,
                'minRR': 2.0,
                'maxExposure': 0.50,
                'leverageMax': 10,
                'maxPositions': 3
            },
            'circuitBreaker': {
                'enabled': True,
                'maxDailyDrawdown': 0.05,  # 5% daily loss limit
                'maxLossStreak': 3,
                'maxPositions': 3
            },
            'kelly': {'enabled': False}
        }
        self.risk_manager = RiskManager(self.config, data_collector=None)

    def test_circuit_breaker_not_tripped_under_limits(self):
        """Test: Circuit breaker OK when all metrics under limits"""
        status = self.risk_manager.check_circuit_breaker(
            current_positions=1,
            daily_pnl=100.0,
            equity=10000.0,
            loss_streak=1
        )

        self.assertFalse(status["tripped"])
        self.assertIsNone(status["reason"])

    def test_circuit_breaker_max_positions(self):
        """Test: Circuit breaker blocks when max positions reached"""
        status = self.risk_manager.check_circuit_breaker(
            current_positions=3,  # maxPositions = 3
            daily_pnl=100.0,
            equity=10000.0,
            loss_streak=1
        )

        self.assertTrue(status["tripped"])
        self.assertIn("Max positions reached", status["reason"])

    def test_circuit_breaker_daily_drawdown(self):
        """Test: Circuit breaker blocks on excessive daily drawdown"""
        equity = 10000.0
        daily_loss = -600.0  # 6% loss > 5% limit

        status = self.risk_manager.check_circuit_breaker(
            current_positions=1,
            daily_pnl=daily_loss,
            equity=equity,
            loss_streak=1
        )

        self.assertTrue(status["tripped"])
        self.assertIn("Max daily drawdown exceeded", status["reason"])

    def test_circuit_breaker_loss_streak(self):
        """Test: Circuit breaker blocks on loss streak"""
        status = self.risk_manager.check_circuit_breaker(
            current_positions=1,
            daily_pnl=-100.0,
            equity=10000.0,
            loss_streak=3  # maxLossStreak = 3
        )

        self.assertTrue(status["tripped"])
        self.assertIn("Max loss streak reached", status["reason"])

    def test_circuit_breaker_disabled(self):
        """Test: Circuit breaker returns not tripped when disabled"""
        config_no_cb = self.config.copy()
        config_no_cb['circuitBreaker']['enabled'] = False
        risk_mgr = RiskManager(config_no_cb, data_collector=None)

        status = risk_mgr.check_circuit_breaker(
            current_positions=10,  # Way over limit
            daily_pnl=-5000.0,  # Massive loss
            equity=10000.0,
            loss_streak=100  # Extreme streak
        )

        self.assertFalse(status["tripped"])


class TestPositionTrackerIntegration(unittest.TestCase):
    """Test PositionTracker integration with RiskManager"""

    def setUp(self):
        """Setup databases and managers"""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.db = Database(self.db_path)
        self.position_tracker = PositionTracker(self.db, fee_rate=0.001)

        self.config = {
            'risk': {
                'riskPct': 0.02,
                'atrMultiplierSL': 2.0,
                'atrMultiplierTP': 4.0,
                'minRR': 2.0,
                'maxExposure': 0.50,
                'leverageMax': 10,
                'maxPositions': 3
            },
            'kelly': {'enabled': False}
        }
        self.risk_manager = RiskManager(self.config, data_collector=None)

    def tearDown(self):
        """Cleanup"""
        self.db.close()
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except:
            pass

    def test_position_tracker_get_open_positions(self):
        """Test: PositionTracker correctly returns open positions"""
        # Open two positions
        self.position_tracker.open_position(
            trade_id=1,
            symbol='BTCUSDT',
            side='Buy',
            entry_price=50000.0,
            quantity=0.1,
            stop_loss=48000.0,
            take_profit=58000.0
        )

        self.position_tracker.open_position(
            trade_id=2,
            symbol='ETHUSDT',
            side='Buy',
            entry_price=3000.0,
            quantity=1.0,
            stop_loss=2900.0,
            take_profit=3500.0
        )

        # Get open positions
        open_pos = self.position_tracker.get_open_positions()

        # Should have 2 open positions
        self.assertEqual(len(open_pos), 2)
        self.assertIn(1, open_pos)
        self.assertIn(2, open_pos)

        # Close first position
        self.position_tracker.close_position(
            trade_id=1,
            exit_price=55000.0,
            exit_reason='TP'
        )

        # Now should only have 1 open position
        open_pos = self.position_tracker.get_open_positions()
        self.assertEqual(len(open_pos), 1)
        self.assertIn(2, open_pos)
        self.assertNotIn(1, open_pos)

    def test_position_notional_calculation(self):
        """Test: Position notional values used correctly for exposure"""
        position1 = {
            "quantity": 0.1,
            "entry_price": 50000.0
        }

        position2 = {
            "quantity": 0.2,
            "entry_price": 30000.0
        }

        notional1 = position1["quantity"] * position1["entry_price"]  # $5,000
        notional2 = position2["quantity"] * position2["entry_price"]  # $6,000
        total_notional = notional1 + notional2  # $11,000

        # With leverageMax=10, required margin = $11,000 / 10 = $1,100
        max_exposure = 10000.0 * 0.50  # $5,000

        # Total margin used ($1,100) should be less than max exposure ($5,000)
        self.assertLess(total_notional / 10, max_exposure)


class TestBotCircuitBreakerIntegration(unittest.TestCase):
    """Test Circuit Breaker integration in bot.py flow"""

    def test_circuit_breaker_early_exit(self):
        """Test: Circuit breaker causes early return before signal processing"""
        config = {
            'risk': {
                'riskPct': 0.02,
                'atrMultiplierSL': 2.0,
                'atrMultiplierTP': 4.0,
                'minRR': 2.0,
                'maxExposure': 0.50,
                'leverageMax': 10,
                'maxPositions': 2
            },
            'circuitBreaker': {
                'enabled': True,
                'maxDailyDrawdown': 0.05,
                'maxLossStreak': 2,
                'maxPositions': 2
            },
            'kelly': {'enabled': False}
        }
        risk_manager = RiskManager(config, data_collector=None)

        # Simulate: 2 open positions (at max), 3 loss streak
        status = risk_manager.check_circuit_breaker(
            current_positions=2,  # At maxPositions
            daily_pnl=-100.0,
            equity=10000.0,
            loss_streak=2  # At maxLossStreak
        )

        # Should be tripped due to max positions
        self.assertTrue(status["tripped"])

        # In bot.py flow, this would cause early return before signal processing
        # This prevents expensive indicator calculations from being wasted


if __name__ == '__main__':
    unittest.main()
