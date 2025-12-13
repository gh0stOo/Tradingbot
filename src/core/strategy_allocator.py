"""Strategy Allocator - Multi-Strategy Coordination"""

import logging
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime, timedelta

from events.signal_event import SignalEvent
from events.order_intent_event import OrderIntentEvent
from core.trading_state import TradingState
from core.position_sizer import PositionSizer

logger = logging.getLogger(__name__)


class StrategyAllocator:
    """
    Multi-Strategy Allocator.
    
    Responsibilities:
    - Prioritizes strategies by regime
    - Prevents conflicts (max 1 active strategy per asset)
    - Limits trades per strategy per day
    - Allocates capital per strategy
    """
    
    def __init__(self, config: dict, trading_state: TradingState) -> None:
        """
        Initialize Strategy Allocator.
        
        Args:
            config: Configuration dictionary
            trading_state: TradingState instance
        """
        self.config = config
        self.strategies_config = config.get("strategies", {})
        self.trading_state = trading_state
        self.position_sizer = PositionSizer()
        
        # Track trades per strategy per day
        self._trades_per_strategy_today: Dict[str, int] = {}
        self._last_reset_date: datetime = datetime.utcnow().date()
        
        # Strategy priorities (from config)
        self._strategy_priorities: Dict[str, int] = {}
        for strategy_name, strategy_config in self.strategies_config.items():
            # Higher weight = higher priority
            weight = strategy_config.get("weight", 1.0)
            self._strategy_priorities[strategy_name] = int(weight * 100)
        
        # Max trades per strategy per day
        self._max_trades_per_strategy = config.get("allocator", {}).get("maxTradesPerStrategy", 5)
        
        logger.info("StrategyAllocator initialized")
    
    def process_signals(self, signals: List[SignalEvent]) -> List[OrderIntentEvent]:
        """
        Process signals from all strategies and generate order intents.
        
        Args:
            signals: List of SignalEvent from all strategies
            
        Returns:
            List of OrderIntentEvent for approved signals
        """
        # Reset daily counters if needed
        self._reset_daily_counters_if_needed()
        
        if not signals:
            return []
        
        # Group signals by symbol
        signals_by_symbol: Dict[str, List[SignalEvent]] = {}
        for signal in signals:
            if signal.symbol not in signals_by_symbol:
                signals_by_symbol[signal.symbol] = []
            signals_by_symbol[signal.symbol].append(signal)
        
        order_intents: List[OrderIntentEvent] = []
        
        for symbol, symbol_signals in signals_by_symbol.items():
            # Check if we already have a position in this asset
            existing_position = self.trading_state.get_position(symbol)
            if existing_position:
                logger.debug(f"Skipping {symbol}: position already exists")
                continue
            
            # Select best signal for this symbol (priority-based)
            best_signal = self._select_best_signal(symbol_signals)
            if not best_signal:
                continue
            
            # Check strategy limits
            if not self._check_strategy_limits(best_signal.strategy_name):
                logger.debug(f"Skipping signal from {best_signal.strategy_name}: daily limit reached")
                continue
            
            # Convert signal to order intent
            order_intent = self._create_order_intent(best_signal)
            if order_intent:
                order_intents.append(order_intent)
                # Increment counter
                self._trades_per_strategy_today[best_signal.strategy_name] = \
                    self._trades_per_strategy_today.get(best_signal.strategy_name, 0) + 1
        
        return order_intents
    
    def _select_best_signal(self, signals: List[SignalEvent]) -> Optional[SignalEvent]:
        """
        Select best signal from multiple signals for same symbol.
        
        Prioritizes by:
        1. Strategy priority (from config weight)
        2. Signal confidence
        """
        if not signals:
            return None
        
        if len(signals) == 1:
            return signals[0]
        
        # Score each signal
        scored_signals = []
        for signal in signals:
            priority = self._strategy_priorities.get(signal.strategy_name, 50)
            confidence_score = signal.confidence * 100
            
            # Combined score: priority (70%) + confidence (30%)
            score = priority * 0.7 + confidence_score * 0.3
            
            scored_signals.append((score, signal))
        
        # Return highest scored signal
        scored_signals.sort(key=lambda x: x[0], reverse=True)
        return scored_signals[0][1]
    
    def _check_strategy_limits(self, strategy_name: str) -> bool:
        """Check if strategy has reached daily trade limit"""
        trades_today = self._trades_per_strategy_today.get(strategy_name, 0)
        return trades_today < self._max_trades_per_strategy
    
    def _create_order_intent(self, signal: SignalEvent) -> Optional[OrderIntentEvent]:
        """
        Convert SignalEvent to OrderIntentEvent.
        
        Position sizing is calculated here using PositionSizer.
        """
        try:
            # Use signal quantity if explicitly provided, otherwise calculate
            if signal.quantity and signal.quantity > 0:
                quantity = signal.quantity
            else:
                # Calculate position size based on risk parameters
                equity = self.trading_state.equity
                risk_config = self.config.get("risk", {})
                max_risk_pct = Decimal(str(risk_config.get("riskPct", 0.002)))  # Default 0.2%
                
                quantity = self.position_sizer.calculate_position_size(
                    equity=equity,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    max_risk_pct=max_risk_pct,
                    side=signal.side
                )
                
                if quantity <= 0:
                    logger.warning(f"Position size calculated as 0 for {signal.symbol}, skipping order intent")
                    return None
                
                # Additional validation: check minimum quantity and trade value
                min_quantity = Decimal("0.001")  # Minimum quantity threshold
                min_trade_value = Decimal("10")  # Minimum $10 trade value
                trade_value = quantity * signal.entry_price
                
                if quantity < min_quantity or trade_value < min_trade_value:
                    logger.warning(
                        f"Position size too small for {signal.symbol}: "
                        f"quantity={quantity}, trade_value={trade_value}, skipping"
                    )
                    return None
            
            order_intent = OrderIntentEvent(
                symbol=signal.symbol,
                side=signal.side,
                quantity=quantity,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                strategy_name=signal.strategy_name,
                signal_event_id=signal.event_id,
                original_signal=signal,
                order_type=signal.order_type,
                time_in_force=signal.time_in_force,
                metadata=signal.metadata,
                source=f"{self.__class__.__name__}",
            )
            
            return order_intent
        
        except Exception as e:
            logger.error(f"Error creating order intent from signal: {e}", exc_info=True)
            return None
    
    def _reset_daily_counters_if_needed(self) -> None:
        """Reset daily counters if new day"""
        today = datetime.utcnow().date()
        if today != self._last_reset_date:
            self._trades_per_strategy_today.clear()
            self._last_reset_date = today
            logger.info("Strategy allocator daily counters reset")

