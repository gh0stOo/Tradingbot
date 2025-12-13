"""Trading State - Single Source of Truth for Trading System"""

import threading
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Optional, List, Callable
from datetime import datetime
from copy import deepcopy

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open trading position"""
    
    symbol: str
    side: str  # "Buy" or "Sell"
    quantity: Decimal
    entry_price: Decimal
    entry_time: datetime
    stop_loss: Decimal
    take_profit: Decimal
    unrealized_pnl: Decimal = Decimal("0")
    position_id: Optional[str] = None  # Internal position ID
    
    def update_pnl(self, current_price: Decimal) -> None:
        """Update unrealized PnL based on current price"""
        if self.side == "Buy":
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        else:  # Sell
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity


@dataclass
class Order:
    """Represents an open order"""
    
    client_order_id: str  # Our UUID for idempotency
    exchange_order_id: Optional[str] = None  # Exchange-assigned ID
    symbol: str = ""
    side: str = ""
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0")
    order_type: str = "Market"
    time_in_force: str = "GTC"
    status: str = "pending"  # pending, submitted, filled, cancelled, rejected
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Optional[Dict] = None


class TradingState:
    """
    Central trading state - Single Source of Truth.
    
    Thread-safe state management for all trading data.
    All state mutations are atomic and protected by locks.
    """
    
    def __init__(self, initial_cash: Decimal = Decimal("10000")) -> None:
        """
        Initialize trading state.
        
        Args:
            initial_cash: Initial cash amount
        """
        self._lock = threading.RLock()  # Reentrant lock for nested calls
        
        # Capital
        self._cash: Decimal = initial_cash
        self._equity: Decimal = initial_cash
        self._peak_equity: Decimal = initial_cash
        
        # Positions and Orders
        self._open_positions: Dict[str, Position] = {}  # symbol -> Position
        self._open_orders: Dict[str, Order] = {}  # client_order_id -> Order
        
        # Exposure
        self._exposure_per_asset: Dict[str, Decimal] = {}
        
        # Trading Control
        self._trading_enabled: bool = False
        
        # Daily Stats
        self._daily_pnl: Decimal = Decimal("0")
        self._trades_today: int = 0
        self._daily_start_equity: Decimal = initial_cash
        self._daily_start_time: datetime = datetime.utcnow()
        
        # Drawdown
        self._drawdown: Decimal = Decimal("0")
        
        self._state_listeners: List[callable] = []  # Callbacks for state changes
        logger.info(f"TradingState initialized with cash={initial_cash}")
    
    def register_state_listener(self, listener: callable) -> None:
        """Register a callback to be called on state changes"""
        self._state_listeners.append(listener)
    
    def _notify_listeners(self) -> None:
        """Notify all registered listeners of state change"""
        for listener in self._state_listeners:
            try:
                listener(self)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error in state listener: {e}", exc_info=True)
    
    # Thread-safe property accessors
    
    @property
    def cash(self) -> Decimal:
        """Get current cash"""
        with self._lock:
            return self._cash
    
    @property
    def equity(self) -> Decimal:
        """Get current equity (cash + unrealized PnL)"""
        with self._lock:
            self._update_equity()
            return self._equity
    
    @property
    def peak_equity(self) -> Decimal:
        """Get peak equity"""
        with self._lock:
            return self._peak_equity
    
    @property
    def drawdown(self) -> Decimal:
        """Get current drawdown"""
        with self._lock:
            self._update_drawdown()
            return self._drawdown
    
    @property
    def drawdown_percent(self) -> Decimal:
        """Get current drawdown as percentage"""
        with self._lock:
            if self._peak_equity > 0:
                return (self._drawdown / self._peak_equity) * Decimal("100")
            return Decimal("0")
    
    @property
    def trading_enabled(self) -> bool:
        """Check if trading is enabled"""
        with self._lock:
            return self._trading_enabled
    
    @property
    def daily_pnl(self) -> Decimal:
        """Get daily PnL"""
        with self._lock:
            return self._daily_pnl
    
    @property
    def trades_today(self) -> int:
        """Get number of trades today"""
        with self._lock:
            return self._trades_today
    
    def get_open_positions(self) -> Dict[str, Position]:
        """Get all open positions (copy)"""
        with self._lock:
            return deepcopy(self._open_positions)
    
    def get_open_orders(self) -> Dict[str, Order]:
        """Get all open orders (copy)"""
        with self._lock:
            return deepcopy(self._open_orders)
    
    def get_exposure_per_asset(self) -> Dict[str, Decimal]:
        """Get exposure per asset (copy)"""
        with self._lock:
            return deepcopy(self._exposure_per_asset)
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol"""
        with self._lock:
            return deepcopy(self._open_positions.get(symbol))
    
    def get_order(self, client_order_id: str) -> Optional[Order]:
        """Get order by client order ID"""
        with self._lock:
            return deepcopy(self._open_orders.get(client_order_id))
    
    # State mutation methods (all atomic)
    
    def enable_trading(self) -> None:
        """Enable trading"""
        with self._lock:
            self._trading_enabled = True
            logger.info("Trading enabled")
    
    def disable_trading(self) -> None:
        """Disable trading"""
        with self._lock:
            self._trading_enabled = False
            logger.info("Trading disabled")
    
    def add_position(
        self,
        symbol: str,
        side: str,
        quantity: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
        position_id: Optional[str] = None
    ) -> bool:
        """
        Add new position (atomic).
        
        Returns:
            True if position was added, False if position already exists
        """
        with self._lock:
            if symbol in self._open_positions:
                logger.warning(f"Position for {symbol} already exists")
                return False
            
            position = Position(
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=entry_price,
                entry_time=datetime.utcnow(),
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_id=position_id
            )
            
            self._open_positions[symbol] = position
            self._update_exposure(symbol, quantity * entry_price)
            self._notify_listeners()
            logger.info(f"Position added: {symbol} {side} {quantity} @ {entry_price}")
            return True
    
    def remove_position(self, symbol: str, realized_pnl: Decimal = Decimal("0")) -> Optional[Position]:
        """
        Remove position (atomic).
        
        Args:
            symbol: Symbol to close
            realized_pnl: Realized PnL from closed position
            
        Returns:
            Removed position or None
        """
        with self._lock:
            if symbol not in self._open_positions:
                return None
            
            position = self._open_positions.pop(symbol)
            self._exposure_per_asset.pop(symbol, None)
            
            # Update daily PnL and trade count
            self._daily_pnl += realized_pnl
            self._trades_today += 1
            self._notify_listeners()
            
            logger.info(f"Position removed: {symbol}, realized_pnl={realized_pnl}")
            return position
    
    def update_position_pnl(self, symbol: str, current_price: Decimal) -> None:
        """Update unrealized PnL for position"""
        with self._lock:
            if symbol in self._open_positions:
                self._open_positions[symbol].update_pnl(current_price)
                self._update_equity()
    
    def add_order(self, order: Order) -> bool:
        """
        Add new order (atomic).
        
        Returns:
            True if order was added, False if order already exists
        """
        with self._lock:
            if order.client_order_id in self._open_orders:
                logger.warning(f"Order {order.client_order_id} already exists")
                return False
            
            self._open_orders[order.client_order_id] = order
            self._notify_listeners()
            logger.info(f"Order added: {order.client_order_id} {order.symbol} {order.side}")
            return True
    
    def update_order(self, client_order_id: str, **updates) -> bool:
        """
        Update order (atomic).
        
        Args:
            client_order_id: Order ID
            **updates: Fields to update
            
        Returns:
            True if order was updated
        """
        with self._lock:
            if client_order_id not in self._open_orders:
                return False
            
            order = self._open_orders[client_order_id]
            for key, value in updates.items():
                if hasattr(order, key):
                    setattr(order, key, value)
            
            self._notify_listeners()
            logger.debug(f"Order updated: {client_order_id}")
            return True
    
    def remove_order(self, client_order_id: str) -> Optional[Order]:
        """
        Remove order (atomic).
        
        Returns:
            Removed order or None
        """
        with self._lock:
            if client_order_id not in self._open_orders:
                return None
            
            order = self._open_orders.pop(client_order_id)
            logger.info(f"Order removed: {client_order_id}")
            return order
    
    def debit_cash(self, amount: Decimal) -> bool:
        """
        Debit cash (atomic).
        
        Returns:
            True if debit was successful
        """
        with self._lock:
            if self._cash < amount:
                logger.warning(f"Insufficient cash: {self._cash} < {amount}")
                return False
            
            self._cash -= amount
            logger.debug(f"Cash debited: {amount}, remaining: {self._cash}")
            return True
    
    def credit_cash(self, amount: Decimal) -> None:
        """Credit cash (atomic)"""
        with self._lock:
            self._cash += amount
            logger.debug(f"Cash credited: {amount}, new balance: {self._cash}")
    
    def reset_daily_stats(self) -> None:
        """Reset daily statistics (called at start of new day)"""
        with self._lock:
            self._daily_pnl = Decimal("0")
            self._trades_today = 0
            self._daily_start_equity = self._equity
            self._daily_start_time = datetime.utcnow()
            logger.info("Daily stats reset")
    
    def snapshot(self) -> Dict:
        """
        Create snapshot of current state (for backtesting/recovery).
        
        Returns:
            Dictionary with state snapshot
        """
        with self._lock:
            self._update_equity()
            self._update_drawdown()
            
            return {
                "cash": float(self._cash),
                "equity": float(self._equity),
                "peak_equity": float(self._peak_equity),
                "drawdown": float(self._drawdown),
                "drawdown_percent": float(self.drawdown_percent),
                "trading_enabled": self._trading_enabled,
                "daily_pnl": float(self._daily_pnl),
                "trades_today": self._trades_today,
                "open_positions": {
                    sym: {
                        "symbol": pos.symbol,
                        "side": pos.side,
                        "quantity": float(pos.quantity),
                        "entry_price": float(pos.entry_price),
                        "unrealized_pnl": float(pos.unrealized_pnl),
                    }
                    for sym, pos in self._open_positions.items()
                },
                "open_orders": {
                    oid: {
                        "client_order_id": ord.client_order_id,
                        "exchange_order_id": ord.exchange_order_id,
                        "symbol": ord.symbol,
                        "side": ord.side,
                        "status": ord.status,
                    }
                    for oid, ord in self._open_orders.items()
                },
                "exposure_per_asset": {
                    sym: float(exp) for sym, exp in self._exposure_per_asset.items()
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def restore_from_snapshot(self, snapshot: Dict) -> None:
        """Restore state from snapshot"""
        with self._lock:
            self._cash = Decimal(str(snapshot["cash"]))
            self._equity = Decimal(str(snapshot["equity"]))
            self._peak_equity = Decimal(str(snapshot["peak_equity"]))
            self._drawdown = Decimal(str(snapshot["drawdown"]))
            self._trading_enabled = snapshot.get("trading_enabled", False)
            self._daily_pnl = Decimal(str(snapshot.get("daily_pnl", 0)))
            self._trades_today = snapshot.get("trades_today", 0)
            
            # Restore positions (simplified - full restoration would need all fields)
            logger.info("State restored from snapshot")
    
    # Private helper methods
    
    def _update_equity(self) -> None:
        """Update equity based on cash and unrealized PnL"""
        unrealized_pnl = sum(
            pos.unrealized_pnl for pos in self._open_positions.values()
        )
        self._equity = self._cash + unrealized_pnl
        
        # Update peak equity
        if self._equity > self._peak_equity:
            self._peak_equity = self._equity
    
    def _update_drawdown(self) -> None:
        """Update drawdown from peak"""
        if self._peak_equity > 0:
            self._drawdown = self._peak_equity - self._equity
        else:
            self._drawdown = Decimal("0")
    
    def _update_exposure(self, symbol: str, exposure: Decimal) -> None:
        """Update exposure for asset"""
        self._exposure_per_asset[symbol] = exposure

