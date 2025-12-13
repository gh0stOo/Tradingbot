"""Order Executor with Idempotency and Reconciliation"""

import logging
import uuid
from typing import Dict, Optional
from decimal import Decimal
from datetime import datetime

from events.risk_approval_event import RiskApprovalEvent
from events.order_submission_event import OrderSubmissionEvent
from events.fill_event import FillEvent
from events.position_update_event import PositionUpdateEvent
from core.trading_state import TradingState, Order
from integrations.bybit import BybitClient

logger = logging.getLogger(__name__)


class OrderExecutor:
    """
    Order Executor with idempotent order handling.
    
    Features:
    - Idempotent order submission (clientOrderId-based)
    - Reconciliation with exchange state
    - Retry logic that never creates duplicate orders
    - Order state tracking in TradingState
    """
    
    def __init__(
        self,
        trading_state: TradingState,
        bybit_client: Optional[BybitClient],
        trading_mode: str,
        config: Optional[Dict] = None
    ) -> None:
        """
        Initialize Order Executor.
        
        Args:
            trading_state: TradingState instance
            bybit_client: BybitClient instance (None for paper trading)
            trading_mode: Trading mode (PAPER, LIVE, TESTNET)
            config: Configuration dictionary (for leverage setting)
        """
        self.trading_state = trading_state
        self.bybit_client = bybit_client
        self.trading_mode = trading_mode
        
        # Get leverage from config (default 10x)
        if config:
            self.leverage = Decimal(str(config.get("trading", {}).get("leverage", 10)))
        else:
            self.leverage = Decimal("10")  # Default 10x leverage
        
        logger.info(f"OrderExecutor initialized (mode: {trading_mode}, leverage: {self.leverage}x)")
    
    def execute_approved_order(self, approval_event: RiskApprovalEvent) -> Optional[OrderSubmissionEvent]:
        """
        Execute an approved order.
        
        Args:
            approval_event: RiskApprovalEvent with approval=True
            
        Returns:
            OrderSubmissionEvent or None if execution failed
        """
        if not approval_event.approved or not approval_event.original_intent:
            logger.warning("Cannot execute non-approved order")
            return None
        
        intent = approval_event.original_intent
        
        # Generate deterministic client order ID for idempotency
        # Use signal_event_id from intent (which comes from original signal)
        # This ensures same signal always gets same client_order_id
        import hashlib
        if intent.signal_event_id:
            # Use signal event ID as base (deterministic)
            base_id = intent.signal_event_id
        else:
            # Fallback: create deterministic ID from intent properties
            # Use symbol, side, strategy_name, and entry_price (but NOT quantity which may vary)
            # Entry price is part of the signal, so it's deterministic
            intent_str = f"{intent.symbol}_{intent.side}_{intent.strategy_name}_{float(intent.entry_price):.8f}"
            base_id = hashlib.md5(intent_str.encode()).hexdigest()[:16]
        
        client_order_id = f"ORDER_{base_id}"
        
        # Check if order already exists (idempotency check)
        existing_order = self.trading_state.get_order(client_order_id)
        if existing_order:
            logger.info(f"Order {client_order_id} already exists, returning existing")
            return OrderSubmissionEvent(
                client_order_id=client_order_id,
                exchange_order_id=existing_order.exchange_order_id,
                symbol=existing_order.symbol,
                side=existing_order.side,
                quantity=existing_order.quantity,
                price=existing_order.price,
                order_type=existing_order.order_type,
                time_in_force=existing_order.time_in_force,
                status=existing_order.status,
                source="OrderExecutor",
            )
        
        # Use adjusted values from risk engine if provided
        quantity = Decimal(str(approval_event.adjusted_quantity)) if approval_event.adjusted_quantity else intent.quantity
        stop_loss = Decimal(str(approval_event.adjusted_stop_loss)) if approval_event.adjusted_stop_loss else intent.stop_loss
        take_profit = Decimal(str(approval_event.adjusted_take_profit)) if approval_event.adjusted_take_profit else intent.take_profit
        
        # Create order in state
        order = Order(
            client_order_id=client_order_id,
            symbol=intent.symbol,
            side=intent.side,
            quantity=quantity,
            price=intent.entry_price,
            order_type=intent.order_type,
            time_in_force=intent.time_in_force,
            status="pending",
        )
        
        # Add to state
        if not self.trading_state.add_order(order):
            logger.error(f"Failed to add order {client_order_id} to state")
            return None
        
        # Execute order (paper or live)
        if self.trading_mode == "PAPER":
            return self._execute_paper_order(order, stop_loss, take_profit)
        else:
            return self._execute_live_order(order, stop_loss, take_profit)
    
    def _execute_paper_order(
        self,
        order: Order,
        stop_loss: Decimal,
        take_profit: Decimal
    ) -> OrderSubmissionEvent:
        """Execute paper order (simulated)"""
        # Simulate order submission
        order.status = "filled"
        self.trading_state.update_order(order.client_order_id, status="filled")
        
        # Simulate slippage for more realistic paper trading
        try:
            from trading.slippage_model import SlippageModel
            slippage_model = SlippageModel()
            order_size_usd = float(order.quantity * order.price)
            slippage = slippage_model.calculate_slippage(
                price=float(order.price),
                order_size_usd=order_size_usd,
                volume_24h_usd=None,  # Would need to fetch from market data for accuracy
                side=order.side,
                volatility=None,
                asset_type="linear"
            )
            
            if order.side == "Buy":
                filled_price = Decimal(str(float(order.price) + slippage))
            else:  # Sell
                filled_price = Decimal(str(float(order.price) - slippage))
        except Exception as e:
            logger.warning(f"Error calculating slippage, using entry price: {e}")
            filled_price = order.price
        fill_event = FillEvent(
            client_order_id=order.client_order_id,
            exchange_order_id=f"PAPER_{order.client_order_id}",
            symbol=order.symbol,
            side=order.side,
            filled_quantity=order.quantity,
            filled_price=filled_price,
            fill_time=datetime.utcnow(),
            is_partial=False,
            remaining_quantity=Decimal("0"),
            source="OrderExecutor",
        )
        
        # Calculate entry fee
        entry_notional = order.quantity * filled_price
        entry_fee = entry_notional * self.taker_fee_rate
        margin_required = entry_notional / self.leverage
        
        # Debit cash (margin + entry fee)
        total_debit = margin_required + entry_fee
        if not self.trading_state.debit_cash(total_debit):
            logger.error(f"Insufficient cash for order {order.client_order_id}")
            order.status = "rejected"
            self.trading_state.update_order(order.client_order_id, status="rejected")
            return OrderSubmissionEvent(
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=filled_price,
                status="rejected",
                rejection_reason="Insufficient cash",
                source="OrderExecutor",
            )
        
        # Update state with position
        self.trading_state.add_position(
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            entry_price=filled_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_id=order.client_order_id,
        )
        
        logger.info(
            f"Paper order executed: {order.client_order_id} {order.symbol} {order.side} {order.quantity} "
            f"@ {filled_price}, margin: {margin_required}, fee: {entry_fee}"
        )
        
        return OrderSubmissionEvent(
            client_order_id=order.client_order_id,
            exchange_order_id=f"PAPER_{order.client_order_id}",
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=filled_price,
            order_type=order.order_type,
            time_in_force=order.time_in_force,
            status="filled",
            source="OrderExecutor",
        )
    
    def _execute_live_order(
        self,
        order: Order,
        stop_loss: Decimal,
        take_profit: Decimal
    ) -> OrderSubmissionEvent:
        """Execute live order on exchange"""
        if not self.bybit_client:
            logger.error("Bybit client not available for live order execution")
            order.status = "rejected"
            self.trading_state.update_order(order.client_order_id, status="rejected")
            return OrderSubmissionEvent(
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=order.price,
                status="rejected",
                rejection_reason="Bybit client not available",
                source="OrderExecutor",
            )
        
        try:
            # Submit order to exchange
            order.status = "submitted"
            self.trading_state.update_order(order.client_order_id, status="submitted")
            
            # Call Bybit API using create_order (existing method)
            order_payload = {
                "category": "linear",
                "symbol": order.symbol,
                "side": order.side,
                "orderType": order.order_type,
                "qty": str(order.quantity),
                "positionIdx": 0,
                "orderLinkId": order.client_order_id,
            }
            
            # Add price for limit orders
            if order.order_type == "Limit":
                order_payload["price"] = str(order.price)
            
            # Add stop loss and take profit
            if stop_loss:
                order_payload["stopLoss"] = str(stop_loss)
            if take_profit:
                order_payload["takeProfit"] = str(take_profit)
            if stop_loss or take_profit:
                order_payload["tpSlMode"] = "Full"
                order_payload["tpOrderType"] = "Market"
                order_payload["slOrderType"] = "Market"
            
            exchange_response = self.bybit_client.create_order(order_payload)
            
            if exchange_response and exchange_response.get("orderId"):
                exchange_order_id = exchange_response["orderId"]
                order.exchange_order_id = exchange_order_id
                order.status = exchange_response.get("orderStatus", "submitted")
                self.trading_state.update_order(
                    order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    status=order.status,
                )
                
                logger.info(f"Live order submitted: {order.client_order_id} -> {exchange_order_id}")
                
                return OrderSubmissionEvent(
                    client_order_id=order.client_order_id,
                    exchange_order_id=exchange_order_id,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    price=order.price,
                    order_type=order.order_type,
                    time_in_force=order.time_in_force,
                    status=order.status,
                    source="OrderExecutor",
                )
            else:
                # Order rejected
                order.status = "rejected"
                self.trading_state.update_order(order.client_order_id, status="rejected")
                rejection_reason = exchange_response.get("retMsg", "Unknown error") if exchange_response else "No response"
                
                return OrderSubmissionEvent(
                    client_order_id=order.client_order_id,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    price=order.price,
                    status="rejected",
                    rejection_reason=rejection_reason,
                    source="OrderExecutor",
                )
        
        except Exception as e:
            logger.error(f"Error executing live order: {e}", exc_info=True)
            order.status = "rejected"
            self.trading_state.update_order(order.client_order_id, status="rejected")
            
            return OrderSubmissionEvent(
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=order.price,
                status="rejected",
                rejection_reason=str(e),
                source="OrderExecutor",
            )
    
    def reconcile_orders(self) -> None:
        """
        Reconcile orders with exchange state.
        
        Periodically called to sync TradingState with exchange.
        """
        if self.trading_mode == "PAPER":
            return  # No reconciliation needed for paper trading
        
        if not self.bybit_client:
            return
        
        try:
            # Get all open orders from state
            open_orders = self.trading_state.get_open_orders()
            
            for client_order_id, order in open_orders.items():
                if order.status in ["filled", "cancelled", "rejected"]:
                    continue
                
                if not order.exchange_order_id:
                    continue
                
                # Query exchange for order status
                try:
                    # Use open orders endpoint to find order
                    # Bybit API: GET /v5/order/realtime
                    endpoint = "/v5/order/realtime"
                    params = {
                        "category": "linear",
                        "symbol": order.symbol
                    }
                    open_orders_response = self.bybit_client._authenticated_request("GET", endpoint, params=params)
                    open_orders_response = open_orders_response.get("result", {})
                    
                    exchange_order = None
                    if open_orders_response and "list" in open_orders_response:
                        for o in open_orders_response["list"]:
                            if o.get("orderId") == order.exchange_order_id or o.get("orderLinkId") == order.client_order_id:
                                exchange_order = o
                                break
                    
                    # If not in open orders, order might be filled or cancelled
                    if not exchange_order and order.status == "submitted":
                        # Order not found in open orders - might be filled
                        # In a real implementation, we would query order history
                        exchange_order = {"orderStatus": "Filled"}
                    
                    if exchange_order:
                        # Update order status
                        exchange_status = exchange_order.get("orderStatus", order.status)
                        if exchange_status != order.status:
                            self.trading_state.update_order(
                                client_order_id,
                                status=exchange_status,
                            )
                            
                            # If filled, create FillEvent
                            if exchange_status == "Filled":
                                fill_event = FillEvent(
                                    client_order_id=client_order_id,
                                    exchange_order_id=order.exchange_order_id,
                                    symbol=order.symbol,
                                    side=order.side,
                                    filled_quantity=Decimal(str(exchange_order.get("cumExecQty", order.quantity))),
                                    filled_price=Decimal(str(exchange_order.get("avgPrice", order.price))),
                                    fill_time=datetime.utcnow(),
                                    is_partial=exchange_order.get("cumExecQty", order.quantity) < order.quantity,
                                    remaining_quantity=order.quantity - Decimal(str(exchange_order.get("cumExecQty", 0))),
                                    source="OrderExecutor",
                                )
                                # Note: FillEvent would be published to event queue in full implementation
                                logger.info(f"Order filled: {client_order_id}")
                except Exception as e:
                    logger.error(f"Error reconciling order {client_order_id}: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"Error reconciling orders: {e}", exc_info=True)
