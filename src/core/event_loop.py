"""Event Loop for Event-Driven Trading Bot"""

import logging
import threading
import time
from typing import List, Optional
from datetime import datetime

from events.event import BaseEvent
from events.queue import EventQueue
from events.dispatcher import EventDispatcher
from events.market_event import MarketEvent
from events.signal_event import SignalEvent
from events.order_intent_event import OrderIntentEvent
from events.risk_approval_event import RiskApprovalEvent
from events.order_submission_event import OrderSubmissionEvent
from events.fill_event import FillEvent
from events.position_update_event import PositionUpdateEvent
from events.kill_switch_event import KillSwitchEvent
from events.system_health_event import SystemHealthEvent

from core.trading_state import TradingState
from core.risk_engine import RiskEngine
from core.strategy_allocator import StrategyAllocator
from core.order_executor import OrderExecutor
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class EventLoop:
    """
    Main event loop for event-driven trading bot.
    
    Processes events from queue and dispatches to handlers.
    """
    
    def __init__(
        self,
        trading_state: TradingState,
        risk_engine: RiskEngine,
        strategy_allocator: StrategyAllocator,
        order_executor: OrderExecutor,
        strategies: List[BaseStrategy],
        config: dict,
        trading_mode: str = "PAPER"
    ) -> None:
        """
        Initialize event loop.
        
        Args:
            trading_state: TradingState instance
            risk_engine: RiskEngine instance
            strategy_allocator: StrategyAllocator instance
            order_executor: OrderExecutor instance
            strategies: List of strategies
            config: Configuration dictionary
        """
        self.trading_state = trading_state
        self.risk_engine = risk_engine
        self.strategy_allocator = strategy_allocator
        self.order_executor = order_executor
        self.strategies = strategies
        self.config = config
        self.trading_mode = trading_mode
        
        # Event infrastructure
        self.event_queue = EventQueue(maxsize=1000)
        self.dispatcher = EventDispatcher()
        
        # Control
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Register event handlers
        self._register_handlers()
        
        logger.info("EventLoop initialized")
    
    def start(self) -> None:
        """Start event loop in background thread"""
        if self.running:
            logger.warning("Event loop already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("Event loop started")
    
    def stop(self) -> None:
        """Stop event loop"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
        logger.info("Event loop stopped")
    
    def publish_event(self, event: BaseEvent) -> bool:
        """Publish event to queue"""
        return self.event_queue.put(event)
    
    def _run_loop(self) -> None:
        """Main event processing loop"""
        logger.info("Event loop thread started")
        
        while self.running:
            try:
                # Get event from queue (non-blocking)
                event = self.event_queue.get(block=True, timeout=0.1)
                
                if event:
                    # Dispatch to handlers
                    self.dispatcher.dispatch(event)
                
            except Exception as e:
                logger.error(f"Error in event loop: {e}", exc_info=True)
                time.sleep(0.1)
        
        logger.info("Event loop thread stopped")
    
    def _register_handlers(self) -> None:
        """Register event handlers"""
        # MarketEvent -> Strategies -> SignalEvent
        self.dispatcher.register_handler(MarketEvent, self._handle_market_event, priority=100)
        
        # SignalEvent -> StrategyAllocator -> OrderIntentEvent
        self.dispatcher.register_handler(SignalEvent, self._handle_signal_event, priority=90)
        
        # OrderIntentEvent -> RiskEngine -> RiskApprovalEvent
        self.dispatcher.register_handler(OrderIntentEvent, self._handle_order_intent, priority=80)
        
        # RiskApprovalEvent -> OrderExecutor -> OrderSubmissionEvent
        self.dispatcher.register_handler(RiskApprovalEvent, self._handle_risk_approval, priority=70)
        
        # KillSwitchEvent -> Disable trading
        self.dispatcher.register_handler(KillSwitchEvent, self._handle_kill_switch, priority=200)
    
    def _handle_market_event(self, event: MarketEvent) -> None:
        """Handle market event - generate signals from strategies"""
        if not self.trading_state.trading_enabled:
            return
        
        all_signals: List[SignalEvent] = []
        
        for strategy in self.strategies:
            if not strategy.is_enabled():
                continue
            
            try:
                signals = strategy.generate_signals(event)
                for signal in signals:
                    # Publish signal event
                    self.publish_event(signal)
            except Exception as e:
                logger.error(f"Error in strategy {strategy.name}: {e}", exc_info=True)
    
    def _handle_signal_event(self, event: SignalEvent) -> None:
        """Handle signal event - process through allocator"""
        try:
            order_intents = self.strategy_allocator.process_signals([event])
            
            for order_intent in order_intents:
                # Publish order intent event
                self.publish_event(order_intent)
        except Exception as e:
            logger.error(f"Error processing signal: {e}", exc_info=True)
    
    def _handle_order_intent(self, event: OrderIntentEvent) -> None:
        """Handle order intent - evaluate through risk engine"""
        try:
            risk_approval = self.risk_engine.evaluate_order_intent(event)
            
            # Publish risk approval event
            self.publish_event(risk_approval)
        except Exception as e:
            logger.error(f"Error evaluating order intent: {e}", exc_info=True)
    
    def _handle_risk_approval(self, event: RiskApprovalEvent) -> None:
        """Handle risk approval - execute order if approved"""
        if not event.approved:
            logger.debug(f"Order rejected by risk engine: {event.reason}")
            return
        
        try:
            order_submission = self.order_executor.execute_approved_order(event)
            
            if order_submission:
                # Publish order submission event
                self.publish_event(order_submission)
                
                # If filled immediately, create fill event
                if order_submission.status == "filled" and self.trading_mode == "PAPER":
                    # Paper trading fills immediately
                    pass  # Fill event would be created in OrderExecutor
        except Exception as e:
            logger.error(f"Error executing order: {e}", exc_info=True)
    
    def _handle_kill_switch(self, event: KillSwitchEvent) -> None:
        """Handle kill switch - disable trading"""
        logger.critical(f"Kill switch activated: {event.reason}")
        self.trading_state.disable_trading()

