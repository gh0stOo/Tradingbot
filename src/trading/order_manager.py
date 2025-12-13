"""Order Management Module"""

import time
import random
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from integrations.bybit import BybitClient
from trading.slippage_model import SlippageModel

logger = logging.getLogger(__name__)

class OrderManager:
    """Manage order execution (Paper and Live)"""

    def __init__(
        self,
        bybit_client: Optional[BybitClient],
        trading_mode: str,
        position_tracker: Optional[Any] = None,
        data_collector: Optional[Any] = None
    ):
        """
        Initialize Order Manager

        Args:
            bybit_client: BybitClient instance (None for paper mode)
            trading_mode: Trading mode (PAPER, LIVE, TESTNET)
            position_tracker: PositionTracker instance for tracking positions
            data_collector: DataCollector instance for logging trades
        """
        self.client = bybit_client
        self.trading_mode = trading_mode
        self.position_tracker = position_tracker
        self.data_collector = data_collector
    
    def execute_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute order (paper or live)
        
        Args:
            order_data: Order data dictionary with symbol, side, qty, price, etc.
            
        Returns:
            Execution result dictionary
        """
        if self.trading_mode == "PAPER":
            return self._execute_paper_order(order_data)
        else:
            return self._execute_live_order(order_data)
    
    def _execute_paper_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute paper trade (simulated)"""
        symbol = order_data["symbol"]
        side = order_data["side"]
        qty = order_data["qty"]
        price = order_data["price"]
        
        # Calculate order size in USD
        order_size_usd = qty * price
        
        # Get volume_24h if available from order_data
        volume_24h_usd = order_data.get("volume24h")
        volatility = order_data.get("volatility")
        asset_type = order_data.get("assetType", "linear")
        
        # Use slippage model to calculate realistic slippage
        slippage = self.slippage_model.calculate_slippage(
            price=price,
            order_size_usd=order_size_usd,
            volume_24h_usd=volume_24h_usd,
            side=side,
            volatility=volatility,
            asset_type=asset_type
        )
        
        if side == "Buy":
            fill_price = price + slippage
        else:
            fill_price = price - slippage

        order_id = f"PAPER_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"

        # Calculate potential PnL
        stop_loss = order_data.get("stopLoss", price)
        take_profit = order_data.get("takeProfit", price)

        potential_profit = abs(take_profit - fill_price) * qty
        potential_loss = abs(fill_price - stop_loss) * qty

        # Handle multi-target exits for paper trading (simulate TP orders)
        multi_targets = order_data.get("multiTargets", {})
        tp_orders_simulated = []
        
        if multi_targets.get("enabled"):
            for tp_key in ["tp1", "tp2", "tp3", "tp4"]:
                if tp_key in multi_targets:
                    tp_config = multi_targets[tp_key]
                    tp_price = tp_config.get("price")
                    tp_qty = tp_config.get("qty")
                    
                    if tp_price and tp_qty and tp_qty > 0:
                        tp_orders_simulated.append({
                            "tp": tp_key,
                            "orderId": f"PAPER_TP_{tp_key}_{int(time.time() * 1000)}_{random.randint(1000, 9999)}",
                            "price": float(tp_price),
                            "qty": float(tp_qty)
                        })
        
        result = {
            "success": True,
            "orderId": order_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": float(fill_price),
            "executionPrice": float(price),
            "slippage": float(slippage),
            "slippagePct": slippage_pct,
            "stopLoss": float(stop_loss),
            "takeProfit": float(take_profit),
            "riskReward": order_data.get("riskReward", 0),
            "notionalValue": float(qty * fill_price),
            "mode": "PAPER",
            "timestamp": int(time.time() * 1000),
            "timestampISO": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
            "potentialProfit": float(potential_profit),
            "potentialLoss": float(potential_loss),
            "multiTargetOrders": tp_orders_simulated if tp_orders_simulated else None
        }

        # Track position if tracker is available
        if self.position_tracker:
            self.position_tracker.open_position(
                trade_id=int(order_id.split("_")[2]),  # Extract numeric ID
                symbol=symbol,
                side=side,
                entry_price=float(fill_price),
                quantity=qty,
                stop_loss=float(stop_loss),
                take_profit=float(take_profit)
            )

        return result

    def _execute_live_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute live order via Bybit API"""
        if not self.client:
            raise ValueError("BybitClient required for live trading")
        
        symbol = order_data["symbol"]
        side = order_data["side"]
        qty = order_data["qty"]
        price = order_data["price"]
        stop_loss = order_data.get("stopLoss")
        take_profit = order_data.get("takeProfit")
        tick_size = order_data.get("tickSize", "0.01")
        
        # Round prices to tick size
        def round_price(p: float, tick: float) -> str:
            return str((int(p / tick) * tick))
        
        # Prepare order payload
        order_payload = {
            "category": "linear",
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": str(qty),
            "positionIdx": 0,
            "orderLinkId": f"bot_{int(time.time() * 1000)}"
        }
        
        # Add stop loss and take profit if provided
        if stop_loss:
            order_payload["stopLoss"] = round_price(stop_loss, float(tick_size))
        if take_profit:
            order_payload["takeProfit"] = round_price(take_profit, float(tick_size))
        
        if stop_loss or take_profit:
            order_payload["tpSlMode"] = "Full"
            order_payload["tpOrderType"] = "Market"
            order_payload["slOrderType"] = "Market"
        
        # Execute main entry order
        try:
            result = self.client.create_order(order_payload)
            order_id = result.get("orderId", "")
            entry_order_link_id = result.get("orderLinkId", f"bot_entry_{int(time.time() * 1000)}")
            
            # Handle multi-target exits if configured
            multi_targets = order_data.get("multiTargets", {})
            tp_order_ids = []
            
            if multi_targets.get("enabled") and self.client:
                # Send separate TP orders for each target
                for tp_key in ["tp1", "tp2", "tp3", "tp4"]:
                    if tp_key in multi_targets:
                        tp_config = multi_targets[tp_key]
                        tp_price = tp_config.get("price")
                        tp_qty = tp_config.get("qty")
                        
                        if tp_price and tp_qty and tp_qty > 0:
                            try:
                                # Create conditional TP order
                                tp_order_payload = {
                                    "category": "linear",
                                    "symbol": symbol,
                                    "side": "Sell" if side == "Buy" else "Buy",  # Opposite side for TP
                                    "orderType": "Market",
                                    "qty": str(tp_qty),
                                    "positionIdx": 0,
                                    "triggerPrice": round_price(tp_price, float(tick_size)),
                                    "triggerBy": "LastPrice",
                                    "orderLinkId": f"bot_tp_{tp_key}_{int(time.time() * 1000)}"
                                }
                                
                                tp_result = self.client.create_order(tp_order_payload)
                                if tp_result and tp_result.get("orderId"):
                                    tp_order_ids.append({
                                        "tp": tp_key,
                                        "orderId": tp_result.get("orderId"),
                                        "price": tp_price,
                                        "qty": tp_qty
                                    })
                            except Exception as tp_error:
                                # Log error but don't fail main order
                                logger.warning(
                                    f"Failed to create {tp_key} order: {tp_error}",
                                    exc_info=True,
                                    extra={"context": {"tp_key": tp_key, "symbol": symbol, "tp_price": tp_price}}
                                )
            
            return {
                "success": True,
                "orderId": order_id,
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "price": float(result.get("price", price)),
                "stopLoss": float(stop_loss) if stop_loss else None,
                "takeProfit": float(take_profit) if take_profit else None,
                "riskReward": order_data.get("riskReward", 0),
                "notionalValue": float(qty * price),
                "mode": self.trading_mode,
                "timestamp": int(time.time() * 1000),
                "timestampISO": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                "orderLinkId": entry_order_link_id,
                "multiTargetOrders": tp_order_ids if tp_order_ids else None
            }
        except Exception as e:
            logger.error(
                f"Error executing order for {symbol}: {e}",
                exc_info=True,
                extra={"context": {"symbol": symbol, "side": side, "error_type": type(e).__name__}}
            )
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "mode": self.trading_mode,
                "timestamp": int(time.time() * 1000),
                "timestampISO": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
            }

