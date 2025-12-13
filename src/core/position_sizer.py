"""Position Sizing Module"""

import logging
from decimal import Decimal
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class PositionSizer:
    """
    Calculate position size based on risk parameters.
    
    Formula: quantity = (equity * risk_pct) / (entry_price - stop_loss)
    """
    
    def calculate_position_size(
        self,
        equity: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        max_risk_pct: Decimal,
        side: str
    ) -> Decimal:
        """
        Calculate position size based on risk percentage.
        
        Args:
            equity: Current account equity
            entry_price: Entry price for the trade
            stop_loss: Stop loss price
            max_risk_pct: Maximum risk percentage (e.g., 0.002 for 0.2%)
            side: "Buy" or "Sell"
            
        Returns:
            Position quantity (can be 0 if invalid)
        """
        try:
            if equity <= 0:
                logger.warning("Invalid equity for position sizing")
                return Decimal("0")
            
            if entry_price <= 0:
                logger.warning("Invalid entry price for position sizing")
                return Decimal("0")
            
            if stop_loss <= 0:
                logger.warning("Invalid stop loss for position sizing")
                return Decimal("0")
            
            # Calculate risk per unit
            if side == "Buy":
                if stop_loss >= entry_price:
                    logger.warning(f"Stop loss ({stop_loss}) must be below entry price ({entry_price}) for long")
                    return Decimal("0")
                risk_per_unit = entry_price - stop_loss
            else:  # Sell
                if stop_loss <= entry_price:
                    logger.warning(f"Stop loss ({stop_loss}) must be above entry price ({entry_price}) for short")
                    return Decimal("0")
                risk_per_unit = stop_loss - entry_price
            
            if risk_per_unit <= 0:
                logger.warning("Invalid risk per unit (must be positive)")
                return Decimal("0")
            
            # Calculate risk amount (excluding fees for now, we'll account for them)
            risk_amount = equity * max_risk_pct
            
            # Account for entry fee in risk calculation
            # Fee reduces the available risk capital
            # If we want to risk X, and fee is F, we need: X = quantity * risk_per_unit + quantity * entry_price * fee_rate
            # Solving for quantity: quantity = X / (risk_per_unit + entry_price * fee_rate)
            taker_fee_rate = Decimal("0.001")  # 0.1% - TODO: Get from config
            effective_risk_per_unit = risk_per_unit + (entry_price * taker_fee_rate)
            
            # Calculate quantity accounting for fees
            quantity = risk_amount / effective_risk_per_unit if effective_risk_per_unit > 0 else Decimal("0")
            
            # Ensure minimum quantity (asset-specific minimums would be better, but use conservative default)
            min_quantity = Decimal("0.001")  # Could be made configurable per asset
            if quantity < min_quantity:
                logger.debug(f"Calculated quantity {quantity} too small (min: {min_quantity}), returning 0")
                return Decimal("0")
            
            # Also check if quantity would result in trade value too small (e.g., < $10)
            trade_value = quantity * entry_price
            min_trade_value = Decimal("10")  # Minimum $10 trade value
            if trade_value < min_trade_value:
                logger.debug(f"Trade value {trade_value} too small (min: {min_trade_value}), returning 0")
                return Decimal("0")
            
            logger.debug(
                f"Position size calculated: quantity={quantity}, "
                f"risk_amount={risk_amount}, risk_per_unit={risk_per_unit}, "
                f"risk_pct={float(max_risk_pct * 100):.2f}%"
            )
            
            return quantity
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}", exc_info=True)
            return Decimal("0")

