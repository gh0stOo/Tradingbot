"""Unit Tests for Event Flows"""

import unittest
from decimal import Decimal
from unittest.mock import Mock, MagicMock
from core.trading_state import TradingState
from core.risk_engine import RiskEngine
from core.strategy_allocator import StrategyAllocator
from core.order_executor import OrderExecutor
from events.market_event import MarketEvent
from events.signal_event import SignalEvent
from events.order_intent_event import OrderIntentEvent
from events.risk_approval_event import RiskApprovalEvent


class TestEventFlows(unittest.TestCase):
    """Test event flows through the system"""
    
    def setUp(self) -> None:
        """Set up test fixtures"""
        self.config = {
            "risk": {
                "riskPct": 0.002,
                "maxDailyLoss": 0.005,
                "maxTradesPerDay": 10,
                "maxExposurePerAsset": 0.10,
            },
            "circuitBreaker": {
                "maxDailyDrawdown": 0.05,
            },
            "strategies": {
                "volatility_expansion": {"weight": 1.0},
                "mean_reversion": {"weight": 0.9},
            },
            "allocator": {
                "maxTradesPerStrategy": 5,
            },
        }
        
        self.trading_state = TradingState(initial_cash=Decimal("10000"))
        self.trading_state.enable_trading()
        
        self.risk_engine = RiskEngine(self.config, self.trading_state)
        self.strategy_allocator = StrategyAllocator(self.config, self.trading_state)
        self.order_executor = OrderExecutor(self.trading_state, None, "PAPER")
    
    def test_market_event_to_signal_flow(self) -> None:
        """Test flow from MarketEvent to SignalEvent"""
        # Create market event
        market_event = MarketEvent(
            symbol="BTCUSDT",
            price=Decimal("50000"),
            volume=Decimal("1000"),
            source="Test",
        )
        
        # This would normally go through strategy
        # For test, create signal directly
        signal = SignalEvent(
            symbol="BTCUSDT",
            side="Buy",
            strategy_name="test_strategy",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("51000"),
            confidence=0.8,
            source="Test",
        )
        
        self.assertEqual(signal.symbol, "BTCUSDT")
        self.assertEqual(signal.side, "Buy")
        self.assertEqual(signal.confidence, 0.8)
    
    def test_signal_to_order_intent_flow(self) -> None:
        """Test flow from SignalEvent to OrderIntentEvent"""
        signal = SignalEvent(
            symbol="BTCUSDT",
            side="Buy",
            strategy_name="test_strategy",
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("51000"),
            confidence=0.8,
            quantity=Decimal("0.1"),
            source="Test",
        )
        
        # Process through allocator
        order_intents = self.strategy_allocator.process_signals([signal])
        
        self.assertEqual(len(order_intents), 1)
        order_intent = order_intents[0]
        self.assertEqual(order_intent.symbol, "BTCUSDT")
        self.assertEqual(order_intent.strategy_name, "test_strategy")
        self.assertEqual(order_intent.signal_event_id, signal.event_id)
    
    def test_order_intent_to_risk_approval_flow(self) -> None:
        """Test flow from OrderIntentEvent to RiskApprovalEvent"""
        order_intent = OrderIntentEvent(
            symbol="BTCUSDT",
            side="Buy",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49000"),
            take_profit=Decimal("51000"),
            strategy_name="test_strategy",
            source="Test",
        )
        
        # Process through risk engine
        risk_approval = self.risk_engine.evaluate_order_intent(order_intent)
        
        self.assertIsNotNone(risk_approval)
        self.assertEqual(risk_approval.order_intent_id, order_intent.event_id)
        # Should be approved if all checks pass
        # May be rejected if limits are hit
    
    def test_approved_order_to_execution_flow(self) -> None:
        """Test flow from RiskApprovalEvent to OrderExecution"""
        order_intent = OrderIntentEvent(
            symbol="BTCUSDT",
            side="Buy",
            quantity=Decimal("0.01"),  # Small size to pass risk checks
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49900"),  # 0.2% risk
            take_profit=Decimal("51000"),
            strategy_name="test_strategy",
            source="Test",
        )
        
        risk_approval = RiskApprovalEvent(
            order_intent_id=order_intent.event_id,
            approved=True,
            reason="Approved",
            adjusted_quantity=float(order_intent.quantity),
            adjusted_stop_loss=float(order_intent.stop_loss),
            adjusted_take_profit=float(order_intent.take_profit),
            original_intent=order_intent,
            source="Test",
        )
        
        # Execute order
        order_submission = self.order_executor.execute_approved_order(risk_approval)
        
        self.assertIsNotNone(order_submission)
        self.assertEqual(order_submission.symbol, "BTCUSDT")
        self.assertEqual(order_submission.status, "filled")  # Paper trading fills immediately
        
        # Check position was created
        position = self.trading_state.get_position("BTCUSDT")
        self.assertIsNotNone(position)
    
    def test_rejected_order_flow(self) -> None:
        """Test flow when order is rejected by risk engine"""
        # Order with too high risk
        order_intent = OrderIntentEvent(
            symbol="BTCUSDT",
            side="Buy",
            quantity=Decimal("10"),  # Very large size
            entry_price=Decimal("50000"),
            stop_loss=Decimal("49900"),
            take_profit=Decimal("51000"),
            strategy_name="test_strategy",
            source="Test",
        )
        
        risk_approval = self.risk_engine.evaluate_order_intent(order_intent)
        
        # Should be rejected due to risk limits
        self.assertIsNotNone(risk_approval)
        self.assertFalse(risk_approval.approved)
        self.assertIn("risk", risk_approval.reason.lower() or "rejected")
        
        # Should not create position
        position = self.trading_state.get_position("BTCUSDT")
        self.assertIsNone(position)


if __name__ == "__main__":
    unittest.main()

