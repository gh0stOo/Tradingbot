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
        
        # FillEvent -> Update position and cash
        self.dispatcher.register_handler(FillEvent, self._handle_fill_event, priority=60)
        
        # PositionUpdateEvent -> Update trading state
        self.dispatcher.register_handler(PositionUpdateEvent, self._handle_position_update, priority=50)
        
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
    
    def _handle_fill_event(self, event: FillEvent) -> None:
        """Handle fill event - create/update position"""
        try:
            from decimal import Decimal
            
            # Get order from state
            order = self.trading_state.get_order(event.client_order_id)
            if not order:
                logger.warning(f"FillEvent for unknown order: {event.client_order_id}")
                return
            
            # Update order status
            self.trading_state.update_order(event.client_order_id, status="filled")
            
            # Create or update position
            existing_position = self.trading_state.get_position(event.symbol)
            
            if existing_position:
                # Update existing position (partial fill or adding to position)
                if event.side == existing_position.side:
                    # Same direction - add to position
                    total_quantity = existing_position.quantity + event.filled_quantity
                    # Recalculate average entry price
                    total_cost = (existing_position.entry_price * existing_position.quantity) + (event.filled_price * event.filled_quantity)
                    new_entry_price = total_cost / total_quantity if total_quantity > 0 else existing_position.entry_price
                    
                    self.trading_state.update_position(
                        event.symbol,
                        quantity=total_quantity,
                        entry_price=new_entry_price
                    )
                else:
                    # Opposite direction - reduce or close position
                    if event.filled_quantity >= existing_position.quantity:
                        # Close position
                        self.trading_state.close_position(event.symbol)
                    else:
                        # Reduce position
                        new_quantity = existing_position.quantity - event.filled_quantity
                        self.trading_state.update_position(
                            event.symbol,
                            quantity=new_quantity
                        )
            else:
                # Create new position
                from core.trading_state import Position
                from datetime import datetime
                
                # Get stop loss and take profit from order metadata
                stop_loss = order.metadata.get("stop_loss") if order.metadata else None
                take_profit = order.metadata.get("take_profit") if order.metadata else None
                
                position = Position(
                    symbol=event.symbol,
                    side=event.side,
                    quantity=event.filled_quantity,
                    entry_price=event.filled_price,
                    entry_time=event.fill_time,
                    stop_loss=Decimal(str(stop_loss)) if stop_loss else None,
                    take_profit=Decimal(str(take_profit)) if take_profit else None
                )
                
                self.trading_state.add_position(event.symbol, position)
            
            # Update cash (margin + fees)
            # This is handled in OrderExecutor for paper trading
            # For live trading, exchange handles this, but we track it
            
            logger.info(f"Position updated for {event.symbol} after fill: {event.filled_quantity} @ {event.filled_price}")
        
        except Exception as e:
            logger.error(f"Error handling fill event: {e}", exc_info=True)
    
    def _handle_position_update(self, event: PositionUpdateEvent) -> None:
        """Handle position update from exchange"""
        try:
            # Check position status (using position_status field)
            if event.position_status == "closed" or event.quantity == Decimal("0"):
                # Position closed by exchange (e.g., via SL/TP)
                existing_position = self.trading_state.get_position(event.symbol)
                if existing_position:
                    realized_pnl = event.realized_pnl if event.realized_pnl else Decimal("0")
                    self.trading_state.close_position(event.symbol, realized_pnl=realized_pnl)
                    logger.info(f"Position closed by exchange: {event.symbol}, realized_pnl={realized_pnl}")
            else:
                # Update position - close and recreate with new values
                existing_position = self.trading_state.get_position(event.symbol)
                if existing_position:
                    # Close existing
                    self.trading_state.close_position(event.symbol, realized_pnl=Decimal("0"))
                    # Recreate with updated values
                    self.trading_state.add_position(
                        symbol=event.symbol,
                        side=event.side,
                        quantity=event.quantity,
                        entry_price=event.entry_price if event.entry_price > 0 else existing_position.entry_price,
                        stop_loss=existing_position.stop_loss,
                        take_profit=existing_position.take_profit
                    )
                    logger.debug(f"Position updated: {event.symbol}")
        
        except Exception as e:
            logger.error(f"Error handling position update: {e}", exc_info=True)
    
    def _handle_kill_switch(self, event: KillSwitchEvent) -> None:
        """Handle kill switch - disable trading"""
        logger.critical(f"Kill switch activated: {event.reason}")
        self.trading_state.disable_trading()

