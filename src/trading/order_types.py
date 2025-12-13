"""Extended Order Types - Limit Orders, Stop Orders, Conditional Orders"""

import time
from typing import Dict, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order type enumeration"""
    MARKET = "Market"
    LIMIT = "Limit"
    STOP_MARKET = "StopMarket"
    STOP_LIMIT = "StopLimit"
    CONDITIONAL = "Conditional"  # OCO - One Cancels Other


class OrderSide(Enum):
    """Order side enumeration"""
    BUY = "Buy"
    SELL = "Sell"


class ExtendedOrderManager:
    """Extended order manager with support for multiple order types"""
    
    def __init__(self, bybit_client):
        """
        Initialize Extended Order Manager
        
        Args:
            bybit_client: BybitClient instance
        """
        self.client = bybit_client
    
    def create_limit_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        limit_price: float,
        time_in_force: str = "GTC",  # GTC, IOC, FOK
        reduce_only: bool = False,
        close_on_trigger: bool = False
    ) -> Dict[str, Any]:
        """
        Create limit order
        
        Args:
            symbol: Trading symbol
            side: Buy or Sell
            qty: Order quantity
            limit_price: Limit price
            time_in_force: Time in force (GTC, IOC, FOK)
            reduce_only: Reduce only flag
            close_on_trigger: Close on trigger flag
            
        Returns:
            Order result dictionary
        """
        order_payload = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Limit",
            "qty": str(qty),
            "price": str(limit_price),
            "timeInForce": time_in_force,
            "positionIdx": 0,
            "reduceOnly": reduce_only,
            "closeOnTrigger": close_on_trigger,
            "orderLinkId": f"limit_{int(time.time() * 1000)}"
        }
        
        return self.client.create_order(order_payload)
    
    def create_stop_market_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        stop_price: float,
        trigger_by: str = "LastPrice",  # LastPrice, IndexPrice, MarkPrice
        reduce_only: bool = False
    ) -> Dict[str, Any]:
        """
        Create stop market order (stop loss order)
        
        Args:
            symbol: Trading symbol
            side: Buy or Sell
            qty: Order quantity
            stop_price: Stop price (trigger price)
            trigger_by: Price type to trigger (LastPrice, IndexPrice, MarkPrice)
            reduce_only: Reduce only flag
            
        Returns:
            Order result dictionary
        """
        order_payload = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(qty),
            "triggerPrice": str(stop_price),
            "triggerBy": trigger_by,
            "positionIdx": 0,
            "reduceOnly": reduce_only,
            "orderLinkId": f"stop_{int(time.time() * 1000)}"
        }
        
        return self.client.create_order(order_payload)
    
    def create_stop_limit_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        limit_price: float,
        stop_price: float,
        trigger_by: str = "LastPrice",
        time_in_force: str = "GTC",
        reduce_only: bool = False
    ) -> Dict[str, Any]:
        """
        Create stop limit order
        
        Args:
            symbol: Trading symbol
            side: Buy or Sell
            qty: Order quantity
            limit_price: Limit price (execution price)
            stop_price: Stop price (trigger price)
            trigger_by: Price type to trigger
            time_in_force: Time in force
            reduce_only: Reduce only flag
            
        Returns:
            Order result dictionary
        """
        order_payload = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Limit",
            "qty": str(qty),
            "price": str(limit_price),
            "triggerPrice": str(stop_price),
            "triggerBy": trigger_by,
            "timeInForce": time_in_force,
            "positionIdx": 0,
            "reduceOnly": reduce_only,
            "orderLinkId": f"stop_limit_{int(time.time() * 1000)}"
        }
        
        return self.client.create_order(order_payload)
    
    def create_trailing_stop(
        self,
        symbol: str,
        qty: float,
        trailing_stop: float,  # Trailing stop distance in price units
        active_price: float,  # Active price (trigger when reached)
        trailing_stop_type: str = "Amount",  # Amount or Percentage
        reduce_only: bool = True
    ) -> Dict[str, Any]:
        """
        Create trailing stop order
        
        Args:
            symbol: Trading symbol
            qty: Order quantity
            trailing_stop: Trailing stop distance
            active_price: Active price
            trailing_stop_type: Amount or Percentage
            reduce_only: Reduce only flag
            
        Returns:
            Order result dictionary
        """
        order_payload = {
            "category": "linear",
            "symbol": symbol,
            "side": "Sell",  # Trailing stop is always to close position
            "orderType": "Market",
            "qty": str(qty),
            "trailingStop": str(trailing_stop),
            "activePrice": str(active_price),
            "trailingStopType": trailing_stop_type,
            "positionIdx": 0,
            "reduceOnly": reduce_only,
            "orderLinkId": f"trailing_{int(time.time() * 1000)}"
        }
        
        return self.client.create_order(order_payload)
    
    def create_oco_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        limit_price: float,
        stop_price: float,
        stop_loss_price: float,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """
        Create OCO (One Cancels Other) order
        Note: Bybit doesn't have native OCO, so we create two conditional orders
        
        Args:
            symbol: Trading symbol
            side: Buy or Sell
            qty: Order quantity
            limit_price: Take profit limit price
            stop_price: Stop loss trigger price
            stop_loss_price: Stop loss execution price
            time_in_force: Time in force
            
        Returns:
            Dictionary with both orders
        """
        # Create take profit limit order
        tp_order = self.create_limit_order(
            symbol=symbol,
            side="Sell" if side == "Buy" else "Buy",
            qty=qty,
            limit_price=limit_price,
            time_in_force=time_in_force,
            reduce_only=True
        )
        
        # Create stop loss order
        sl_order = self.create_stop_market_order(
            symbol=symbol,
            side="Sell" if side == "Buy" else "Buy",
            qty=qty,
            stop_price=stop_price,
            reduce_only=True
        )
        
        return {
            "take_profit_order": tp_order,
            "stop_loss_order": sl_order,
            "type": "OCO"
        }

