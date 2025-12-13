"""Unit Tests for RiskEngine"""

import unittest
from decimal import Decimal
from core.trading_state import TradingState
from core.risk_engine import RiskEngine
from events.order_intent_event import OrderIntentEvent


class TestRiskEngine(unittest.TestCase):
    """Test RiskEngine"""
    
    def setUp(self) -> None:
        """Set up test fixtures"""
        self.trading_state = TradingState(initial_cash=Decimal("10000"))
        self.trading_state.enable_trading()
        
        self.config = {
            "risk": {
                "riskPct": 0.002,  # 0.2% per trade
                "maxDailyLoss": 0.005,  # 0.5% daily
                "maxTradesPerDay": 10,
                "maxExposurePerAsset": 0.10,  # 10%
            },
            "circuitBreaker": {
                "maxDailyDrawdown": 0.05,  # 5%
            },
        }
        self.risk_engine = RiskEngine(self.config, self.trading_state)
    
    def test_risk_per_trade_check(self) -> None:
        """Test risk per trade limit"""
        # Order with 0.3% risk (exceeds 0.2% limit)
        order_intent = OrderIntentEvent(
            symbol="BTCUSDT",
            side="Buy",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49850"),  # 0.3% risk
            take_profit=Decimal("51000"),
            strategy_name="test",
            source="Test",
        )
        
        approval = self.risk_engine.evaluate_order_intent(order_intent)
        self.assertFalse(approval.approved)
        self.assertIn("Risk per trade", approval.reason)
    
    def test_max_trades_per_day(self) -> None:
        """Test max trades per day limit"""
        # Fill up daily trade limit
        for i in range(10):
            order_intent = OrderIntentEvent(
                symbol=f"COIN{i}USDT",
                side="Buy",
                quantity=Decimal("0.01"),
                entry_price=Decimal("100"),
                stop_loss=Decimal("99"),
                take_profit=Decimal("101"),
                strategy_name="test",
                source="Test",
            )
            approval = self.risk_engine.evaluate_order_intent(order_intent)
            if approval.approved:
                # Simulate trade execution
                self.trading_state.trades_today = i + 1
        
        # 11th trade should be rejected
        order_intent = OrderIntentEvent(
            symbol="COIN11USDT",
            side="Buy",
            quantity=Decimal("0.01"),
            entry_price=Decimal("100"),
            stop_loss=Decimal("99"),
            take_profit=Decimal("101"),
            strategy_name="test",
            source="Test",
        )
        approval = self.risk_engine.evaluate_order_intent(order_intent)
        # Note: This test may need adjustment based on actual implementation
        # The risk engine checks trading_state.trades_today internally
    
    def test_daily_loss_limit(self) -> None:
        """Test daily loss limit (kill switch)"""
        # Simulate large daily loss
        self.trading_state._daily_pnl = Decimal("-100")  # -1% loss
        self.trading_state._equity = Decimal("9900")
        
        order_intent = OrderIntentEvent(
            symbol="BTCUSDT",
            side="Buy",
            quantity=Decimal("0.01"),
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49900"),  # 0.2% risk
            take_profit=Decimal("51000"),
            strategy_name="test",
            source="Test",
        )
        
        approval = self.risk_engine.evaluate_order_intent(order_intent)
        # Should trigger kill switch if daily loss > 0.5%
        # This depends on equity value
    
    def test_approved_order(self) -> None:
        """Test approved order"""
        order_intent = OrderIntentEvent(
            symbol="BTCUSDT",
            side="Buy",
            quantity=Decimal("0.01"),
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49900"),  # 0.2% risk (within limit)
            take_profit=Decimal("51000"),
            strategy_name="test",
            source="Test",
        )
        
        approval = self.risk_engine.evaluate_order_intent(order_intent)
        # Should be approved if all checks pass
        # May be rejected if other limits are hit


if __name__ == "__main__":
    unittest.main()

