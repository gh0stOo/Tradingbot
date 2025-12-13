"""Position Monitor - Checks Stop-Loss and Take-Profit"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime

from core.trading_state import TradingState, Position
from events.position_update_event import PositionUpdateEvent
from integrations.bybit import BybitClient

logger = logging.getLogger(__name__)


class PositionMonitor:
    """
    Monitors open positions and checks for stop-loss/take-profit hits.
    """
    
    def __init__(
        self,
        trading_state: TradingState,
        bybit_client: Optional[BybitClient],
        trading_mode: str,
        config: Optional[Dict] = None
    ) -> None:
        """
        Initialize Position Monitor.
        
        Args:
            trading_state: TradingState instance
            bybit_client: BybitClient instance (None for paper trading)
            trading_mode: Trading mode (PAPER, LIVE, TESTNET)
            config: Configuration dictionary
        """
        self.trading_state = trading_state
        self.bybit_client = bybit_client
        self.trading_mode = trading_mode
        self.config = config or {}
        
        # Fee settings
        self.taker_fee = Decimal(str(self.config.get("trading", {}).get("takerFee", 0.001)))  # 0.1%
        
        logger.info("PositionMonitor initialized")
    
    def check_positions(self, current_prices: Dict[str, Decimal]) -> List[Dict]:
        """
        Check all open positions for stop-loss/take-profit hits.
        
        Args:
            current_prices: Dict mapping symbol to current price
            
        Returns:
            List of position exit events (dicts with symbol, exit_reason, exit_price, realized_pnl)
        """
        exits = []
        open_positions = self.trading_state.get_open_positions()
        
        for symbol, position in open_positions.items():
            if symbol not in current_prices:
                logger.warning(f"No current price available for {symbol}, skipping position check")
                continue
            
            current_price = current_prices[symbol]
            
            # Validate price is positive
            if current_price <= 0:
                logger.warning(f"Invalid current price {current_price} for {symbol}, skipping")
                continue
            
            try:
                # Check stop loss first (more important)
                if self._check_stop_loss(position, current_price):
                    exit_info = self._close_position(position, current_price, "Stop Loss")
                    if exit_info:
                        exits.append(exit_info)
                        continue  # Position closed, skip take profit check
                    else:
                        logger.error(f"Failed to close position {symbol} on stop loss, will retry next check")
                
                # Check take profit (only if stop loss didn't trigger)
                elif self._check_take_profit(position, current_price):
                    exit_info = self._close_position(position, current_price, "Take Profit")
                    if exit_info:
                        exits.append(exit_info)
                        continue  # Position closed
                    else:
                        logger.error(f"Failed to close position {symbol} on take profit, will retry next check")
                
                # Update unrealized PnL if position still open
                else:
                    self.trading_state.update_position_pnl(symbol, current_price)
                    
            except Exception as e:
                logger.error(f"Error checking position {symbol}: {e}", exc_info=True)
                # Continue with other positions even if one fails
        
        return exits
    
    def _check_stop_loss(self, position: Position, current_price: Decimal) -> bool:
        """Check if stop loss is hit"""
        # Validate stop loss is set
        if not position.stop_loss or position.stop_loss <= 0:
            return False  # No stop loss set, cannot trigger
        
        if position.side == "Buy":
            return current_price <= position.stop_loss
        else:  # Sell
            return current_price >= position.stop_loss
    
    def _check_take_profit(self, position: Position, current_price: Decimal) -> bool:
        """Check if take profit is hit"""
        # Validate take profit is set
        if not position.take_profit or position.take_profit <= 0:
            return False  # No take profit set, cannot trigger
        
        if position.side == "Buy":
            return current_price >= position.take_profit
        else:  # Sell
            return current_price <= position.take_profit
    
    def _close_position(
        self,
        position: Position,
        exit_price: Decimal,
        exit_reason: str
    ) -> Optional[Dict]:
        """
        Close a position and calculate realized PnL.
        
        Returns:
            Dict with exit information or None if close failed
        """
        try:
            # Calculate realized PnL
            if position.side == "Buy":
                pnl_before_fees = (exit_price - position.entry_price) * position.quantity
            else:  # Sell
                pnl_before_fees = (position.entry_price - exit_price) * position.quantity
            
            # Calculate fees (entry + exit)
            entry_notional = position.entry_price * position.quantity
            exit_notional = exit_price * position.quantity
            entry_fee = entry_notional * self.taker_fee
            exit_fee = exit_notional * self.taker_fee
            total_fees = entry_fee + exit_fee
            
            realized_pnl = pnl_before_fees - total_fees
            
            # Remove position from state
            removed_position = self.trading_state.remove_position(position.symbol, realized_pnl)
            
            if removed_position:
                # Return margin + PnL to cash
                margin_used = (position.entry_price * position.quantity) / Decimal(str(self.config.get("trading", {}).get("leverage", 10)))
                cash_to_return = margin_used + realized_pnl
                
                # Only credit if positive (realized loss reduces cash)
                if cash_to_return > 0:
                    self.trading_state.credit_cash(cash_to_return)
                elif cash_to_return < 0:
                    # Loss - debit cash
                    self.trading_state.debit_cash(abs(cash_to_return))
                
                logger.info(
                    f"Position closed: {position.symbol} {position.side} "
                    f"Exit: {exit_reason} @ {exit_price}, PnL: {realized_pnl:.2f}, Fees: {total_fees:.2f}"
                )
                
                return {
                    "symbol": position.symbol,
                    "side": position.side,
                    "entry_price": position.entry_price,
                    "exit_price": exit_price,
                    "quantity": position.quantity,
                    "realized_pnl": realized_pnl,
                    "fees": total_fees,
                    "exit_reason": exit_reason,
                    "timestamp": datetime.utcnow()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error closing position {position.symbol}: {e}", exc_info=True)
            return None

