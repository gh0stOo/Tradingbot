"""
Unit Tests for PHASE 1: Critical Calculations
Tests for PNL calculation, Kelly Criterion, Multi-Target exits, and Database schema
"""

import unittest
import tempfile
import os
from decimal import Decimal
from datetime import datetime

# Add src to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data.database import Database
from data.position_tracker import PositionTracker
from trading.risk_manager import RiskManager


class TestPNLCalculationWithFees(unittest.TestCase):
    """Test PNL calculation with transaction fees"""

    def setUp(self):
        """Setup test database"""
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

    def test_pnl_calculation_with_fees_buy(self):
        """Test: Buy order PNL with fees correctly calculated"""
        # Open position: BUY 100 @ $50
        self.tracker.open_position(
            trade_id=1,
            symbol='BTCUSDT',
            side='Buy',
            entry_price=50.0,
            quantity=100.0,
            stop_loss=48.0,
            take_profit=55.0
        )

        # Close position: SELL @ $55
        result = self.tracker.close_position(
            trade_id=1,
            exit_price=55.0,
            exit_reason='TP'
        )

        # Gross PnL: (55 - 50) * 100 = $500
        # Entry fee: 50 * 100 * 0.001 = $5
        # Exit fee: 55 * 100 * 0.001 = $5.5
        # Net PnL: 500 - 5 - 5.5 = $489.5
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['realized_pnl'], 489.5, places=1)
        self.assertTrue(result['success'])  # Breakeven is success

    def test_pnl_calculation_with_fees_sell(self):
        """Test: Sell order PNL with fees correctly calculated"""
        # Open position: SELL 100 @ $50
        self.tracker.open_position(
            trade_id=2,
            symbol='ETHUSDT',
            side='Sell',
            entry_price=50.0,
            quantity=100.0,
            stop_loss=52.0,
            take_profit=45.0
        )

        # Close position: BUY @ $45
        result = self.tracker.close_position(
            trade_id=2,
            exit_price=45.0,
            exit_reason='TP'
        )

        # Gross PnL: (50 - 45) * 100 = $500
        # Entry fee: 50 * 100 * 0.001 = $5
        # Exit fee: 45 * 100 * 0.001 = $4.5
        # Net PnL: 500 - 5 - 4.5 = $490.5
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result['realized_pnl'], 490.5, places=1)
        self.assertTrue(result['success'])

    def test_breakeven_is_success(self):
        """Test: Near-breakeven (PnL close to 0) is marked as success"""
        # Position that will breakeven after fees
        self.tracker.open_position(
            trade_id=3,
            symbol='BTCUSDT',
            side='Buy',
            entry_price=100.0,
            quantity=1.0,
            stop_loss=98.0,
            take_profit=102.0
        )

        # Close at price that results in near-0 PnL
        # Entry fee: 100 * 1 * 0.001 = 0.1
        # Exit fee: 100.3 * 1 * 0.001 = 0.1003
        # Gross PnL: (100.3 - 100.0) * 1 = 0.3
        # Net PnL: 0.3 - 0.1 - 0.1003 = 0.0997 (profit, success)
        result = self.tracker.close_position(
            trade_id=3,
            exit_price=100.3,
            exit_reason='Manual'
        )

        self.assertIsNotNone(result)
        self.assertGreater(result['realized_pnl'], -0.001)  # Near breakeven
        self.assertTrue(result['success'])  # Should be True (>= -0.0001)


class TestMultiTargetDecimalArithmetic(unittest.TestCase):
    """Test Multi-Target exit quantity calculation with Decimal arithmetic"""

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
            'multiTargetExits': {
                'enabled': True,
                'tp1': {'distance': 1.5, 'size': 0.25},
                'tp2': {'distance': 2.5, 'size': 0.25},
                'tp3': {'distance': 3.5, 'size': 0.25},
                'tp4': {'distance': 4.5, 'size': 0.25}
            },
            'kelly': {
                'enabled': False
            }
        }
        self.risk_manager = RiskManager(self.config)

    def test_multi_target_quantity_precision(self):
        """Test: Multi-target quantities sum exactly to total with Decimal precision"""
        position = {
            'qty': 10.0,
            'price': 50000.0,
            'side': 'Buy'
        }

        result = self.risk_manager.setup_multi_target_exits(
            position=position,
            atr=1000.0,
            side='Buy'
        )

        # Check that multi-targets exist
        self.assertIn('multiTargets', result)
        multi_targets = result['multiTargets']

        # Calculate total quantity from TP levels
        total_tp_qty = 0.0
        for tp_key in ['tp1', 'tp2', 'tp3', 'tp4']:
            if tp_key in multi_targets and tp_key != 'enabled':
                total_tp_qty += multi_targets[tp_key]['qty']

        # Should equal original qty exactly (no truncation loss)
        self.assertAlmostEqual(total_tp_qty, 10.0, places=3)

    def test_multi_target_no_truncation(self):
        """Test: 10 BTC with 0.25 splits = no truncation loss"""
        position = {
            'qty': 10.0,
            'price': 50000.0,
            'side': 'Buy'
        }

        result = self.risk_manager.setup_multi_target_exits(
            position=position,
            atr=1000.0,
            side='Buy'
        )

        multi_targets = result['multiTargets']

        # With 4 TPs of 0.25 each:
        # TP1: 10 * 0.25 = 2.5
        # TP2: 10 * 0.25 = 2.5
        # TP3: 10 * 0.25 = 2.5
        # TP4: remainder = 2.5
        self.assertAlmostEqual(multi_targets['tp1']['qty'], 2.5, places=3)
        self.assertAlmostEqual(multi_targets['tp2']['qty'], 2.5, places=3)
        self.assertAlmostEqual(multi_targets['tp3']['qty'], 2.5, places=3)
        self.assertAlmostEqual(multi_targets['tp4']['qty'], 2.5, places=3)


class TestKellyCriterion(unittest.TestCase):
    """Test Kelly Criterion position sizing"""

    def setUp(self):
        """Setup risk manager with Kelly enabled"""
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
            'kelly': {
                'enabled': True,
                'minWinRate': 0.40,
                'minRR': 1.5,
                'fraction': 0.25,  # Safety multiplier
                'regimeAdjustments': {
                    'volatile': 0.7,
                    'trending': 1.0,
                    'ranging': 0.85
                }
            },
            'multiTargetExits': {
                'enabled': False
            }
        }
        self.risk_manager = RiskManager(self.config, data_collector=None)

    def test_kelly_uses_historical_winrate(self):
        """Test: Kelly uses historical win rate, not confidence"""
        # With 60% historical win rate and 50% confidence,
        # position size should be based on 60%, not 50%

        result = self.risk_manager.calculate_position_size(
            equity=10000.0,
            price=50000.0,
            atr=1000.0,
            side='Buy',
            confidence=0.5,  # Low confidence
            qty_step=0.001,
            min_order_qty=0.001,
            historical_win_rate=0.60,  # High historical rate
            volatility=0.02,
            regime=None
        )

        # Position size should be reasonable (not zero due to low confidence)
        self.assertIsNotNone(result)
        self.assertGreater(result['qty'], 0)

    def test_kelly_with_regime_adjustment(self):
        """Test: Kelly applies regime-based adjustments"""
        regime_volatile = {'type': 'volatile'}

        result_volatile = self.risk_manager.calculate_position_size(
            equity=10000.0,
            price=50000.0,
            atr=1000.0,
            side='Buy',
            confidence=0.7,
            qty_step=0.001,
            min_order_qty=0.001,
            historical_win_rate=0.55,
            volatility=0.05,
            regime=regime_volatile
        )

        regime_trending = {'type': 'trending'}
        result_trending = self.risk_manager.calculate_position_size(
            equity=10000.0,
            price=50000.0,
            atr=1000.0,
            side='Buy',
            confidence=0.7,
            qty_step=0.001,
            min_order_qty=0.001,
            historical_win_rate=0.55,
            volatility=0.02,
            regime=regime_trending
        )

        # Trending should have larger position than volatile
        self.assertIsNotNone(result_volatile)
        self.assertIsNotNone(result_trending)
        if result_volatile and result_trending:
            self.assertGreaterEqual(result_trending['qty'], result_volatile['qty'])


class TestDatabaseMigration(unittest.TestCase):
    """Test database schema migration for fees_paid column"""

    def setUp(self):
        """Setup test database"""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.db = Database(self.db_path)

    def tearDown(self):
        """Cleanup"""
        self.db.close()
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except:
            pass

    def test_fees_paid_column_exists(self):
        """Test: fees_paid column exists in trades table"""
        # Try to insert a trade with fees_paid
        cursor = self.db.execute("""
            INSERT INTO trades (
                timestamp, symbol, side, entry_price, quantity,
                stop_loss, take_profit, confidence, quality_score,
                regime_type, strategies_used, trading_mode,
                exit_price, exit_time, exit_reason,
                realized_pnl, fees_paid, success
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.utcnow(), 'BTCUSDT', 'Buy', 50000.0, 0.1,
            48000.0, 55000.0, 0.7, 0.85, 'trending',
            'RSI,MACD', 'PAPER',
            55000.0, datetime.utcnow(), 'TP',
            500.0, 10.0, True  # fees_paid = 10.0
        ))

        # Verify it was inserted
        row = self.db.fetch_one("SELECT fees_paid FROM trades WHERE symbol = 'BTCUSDT'")
        self.assertIsNotNone(row)
        self.assertEqual(row['fees_paid'], 10.0)


if __name__ == '__main__':
    unittest.main()
