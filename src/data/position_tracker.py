"""Position Tracker Module - Tracking opened and closed positions"""

from typing import Dict, Optional, Any
from datetime import datetime
import logging

from data.database import Database

logger = logging.getLogger(__name__)


class PositionTracker:
    """Tracks open and closed positions with PnL calculation"""

    def __init__(self, db: Database):
        """
        Initialize Position Tracker

        Args:
            db: Database instance
        """
        self.db = db
        self.open_positions: Dict[int, Dict[str, Any]] = {}  # trade_id -> position data

    def open_position(
        self,
        trade_id: int,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        stop_loss: float,
        take_profit: float
    ) -> bool:
        """
        Track opened position

        Args:
            trade_id: Trade ID
            symbol: Trading symbol
            side: Buy or Sell
            entry_price: Entry price
            quantity: Position quantity
            stop_loss: Stop loss price
            take_profit: Take profit price

        Returns:
            True if successful
        """
        try:
            position = {
                "trade_id": trade_id,
                "symbol": symbol,
                "side": side,
                "entry_price": entry_price,
                "quantity": quantity,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "entry_time": datetime.utcnow(),
                "status": "open"
            }

            self.open_positions[trade_id] = position
            logger.info(f"Position opened: {symbol} {side} @ {entry_price} (Trade ID: {trade_id})")
            return True
        except Exception as e:
            logger.error(f"Error opening position: {e}")
            return False

    def close_position(
        self,
        trade_id: int,
        exit_price: float,
        exit_reason: str = "Manual",
        exit_time: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Close position and calculate PnL

        Args:
            trade_id: Trade ID
            exit_price: Exit price
            exit_reason: Reason for exit (TP/SL/Manual)
            exit_time: Exit time (default: now)

        Returns:
            Position data with PnL or None if failed
        """
        try:
            exit_time = exit_time or datetime.utcnow()

            if trade_id not in self.open_positions:
                logger.warning(f"Trade {trade_id} not found in open positions")
                return None

            position = self.open_positions[trade_id]

            # Calculate PnL
            side = position["side"]
            quantity = position["quantity"]
            entry_price = position["entry_price"]

            if side == "Buy":
                realized_pnl = (exit_price - entry_price) * quantity
            else:  # Sell
                realized_pnl = (entry_price - exit_price) * quantity

            success = realized_pnl > 0

            # Update position in database
            self.db.execute("""
                UPDATE trades
                SET exit_price = ?, exit_time = ?,
                    exit_reason = ?, realized_pnl = ?,
                    success = ?
                WHERE id = ?
            """, (exit_price, exit_time, exit_reason, realized_pnl, success, trade_id))

            position.update({
                "exit_price": exit_price,
                "exit_time": exit_time,
                "exit_reason": exit_reason,
                "realized_pnl": realized_pnl,
                "success": success,
                "status": "closed"
            })

            logger.info(
                f"Position closed: {position['symbol']} "
                f"PnL={realized_pnl:.2f} ({exit_reason}) "
                f"(Trade ID: {trade_id})"
            )

            return position
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return None

    def get_position(self, trade_id: int) -> Optional[Dict[str, Any]]:
        """
        Get position by trade ID

        Args:
            trade_id: Trade ID

        Returns:
            Position data or None
        """
        return self.open_positions.get(trade_id)

    def get_open_positions(self) -> Dict[int, Dict[str, Any]]:
        """
        Get all open positions

        Returns:
            Dictionary of open positions
        """
        return {
            tid: pos for tid, pos in self.open_positions.items()
            if pos.get("status") == "open"
        }

    def calculate_pnl(self, trade_id: int) -> Optional[float]:
        """
        Calculate unrealized PnL for open position

        Args:
            trade_id: Trade ID
            current_price: Current market price

        Returns:
            Unrealized PnL or None
        """
        position = self.open_positions.get(trade_id)
        if not position or position.get("status") != "open":
            return None

        # Note: This would need current price from market data
        # For now just return the structure
        logger.debug(f"Calculating PnL for position {trade_id}")
        return None

    def get_position_stats(self) -> Dict[str, Any]:
        """
        Get statistics about positions

        Returns:
            Statistics dictionary
        """
        open_positions = self.get_open_positions()

        stats = {
            "total_open": len(open_positions),
            "total_buy": sum(1 for p in open_positions.values() if p.get("side") == "Buy"),
            "total_sell": sum(1 for p in open_positions.values() if p.get("side") == "Sell"),
            "symbols": list(set(p.get("symbol") for p in open_positions.values()))
        }

        return stats

    def clear_closed_positions(self):
        """Remove closed positions from memory to save space"""
        closed_ids = [
            tid for tid, pos in self.open_positions.items()
            if pos.get("status") == "closed"
        ]

        for tid in closed_ids:
            del self.open_positions[tid]

        if closed_ids:
            logger.info(f"Cleared {len(closed_ids)} closed positions from memory")
