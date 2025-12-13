"""State Persistence for TradingState"""

import logging
from typing import Optional
from decimal import Decimal
from datetime import datetime
import json
from core.trading_state import TradingState, Position, Order
from data.database import Database

logger = logging.getLogger(__name__)


class StatePersistence:
    """
    Persist TradingState to database for recovery.
    
    Automatically saves state changes and allows restoration on startup.
    """
    
    def __init__(self, db: Database, state: TradingState) -> None:
        """
        Initialize state persistence.
        
        Args:
            db: Database instance
            state: TradingState instance to persist
        """
        self.db = db
        self.state = state
        self._create_schema()
        logger.info("StatePersistence initialized")
    
    def _create_schema(self) -> None:
        """Create state persistence tables"""
        try:
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS trading_state_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    cash REAL NOT NULL,
                    equity REAL NOT NULL,
                    peak_equity REAL NOT NULL,
                    drawdown REAL NOT NULL,
                    trading_enabled INTEGER NOT NULL,
                    daily_pnl REAL NOT NULL,
                    trades_today INTEGER NOT NULL,
                    snapshot_data TEXT NOT NULL,
                    UNIQUE(timestamp)
                )
            """)
            
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS trading_state_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_time TEXT NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    unrealized_pnl REAL NOT NULL,
                    position_id TEXT,
                    FOREIGN KEY(snapshot_id) REFERENCES trading_state_snapshots(id) ON DELETE CASCADE
                )
            """)
            
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS trading_state_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER,
                    client_order_id TEXT NOT NULL,
                    exchange_order_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    order_type TEXT NOT NULL,
                    time_in_force TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(snapshot_id) REFERENCES trading_state_snapshots(id) ON DELETE CASCADE,
                    UNIQUE(client_order_id)
                )
            """)
            
            self.db.commit()
        except Exception as e:
            logger.error(f"Error creating state persistence schema: {e}")
    
    def save_state(self) -> bool:
        """
        Save current state to database.
        
        Returns:
            True if successful
        """
        try:
            snapshot = self.state.snapshot()
            timestamp = datetime.utcnow().isoformat()
            
            # Save main snapshot
            cursor = self.db.execute("""
                INSERT OR REPLACE INTO trading_state_snapshots 
                (timestamp, cash, equity, peak_equity, drawdown, trading_enabled, 
                 daily_pnl, trades_today, snapshot_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                snapshot["cash"],
                snapshot["equity"],
                snapshot["peak_equity"],
                snapshot["drawdown"],
                1 if snapshot["trading_enabled"] else 0,
                snapshot["daily_pnl"],
                snapshot["trades_today"],
                json.dumps(snapshot),
            ))
            
            snapshot_id = cursor.lastrowid
            
            # Save positions
            for symbol, pos_data in snapshot["open_positions"].items():
                # Get full position from state
                position = self.state.get_position(symbol)
                if position:
                    self.db.execute("""
                        INSERT INTO trading_state_positions
                        (snapshot_id, symbol, side, quantity, entry_price, entry_time,
                         stop_loss, take_profit, unrealized_pnl, position_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        snapshot_id,
                        position.symbol,
                        position.side,
                        float(position.quantity),
                        float(position.entry_price),
                        position.entry_time.isoformat(),
                        float(position.stop_loss),
                        float(position.take_profit),
                        float(position.unrealized_pnl),
                        position.position_id or "",
                    ))
            
            # Save orders
            for client_order_id, ord_data in snapshot["open_orders"].items():
                order = self.state.get_order(client_order_id)
                if order:
                    self.db.execute("""
                        INSERT OR REPLACE INTO trading_state_orders
                        (snapshot_id, client_order_id, exchange_order_id, symbol, side,
                         quantity, price, order_type, time_in_force, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        snapshot_id,
                        order.client_order_id,
                        order.exchange_order_id or "",
                        order.symbol,
                        order.side,
                        float(order.quantity),
                        float(order.price),
                        order.order_type,
                        order.time_in_force,
                        order.status,
                        order.created_at.isoformat(),
                    ))
            
            self.db.commit()
            logger.debug(f"State saved to database (snapshot_id={snapshot_id})")
            return True
        
        except Exception as e:
            logger.error(f"Error saving state: {e}", exc_info=True)
            return False
    
    def restore_latest_state(self) -> bool:
        """
        Restore latest state from database.
        
        Returns:
            True if successful
        """
        try:
            # Get latest snapshot
            cursor = self.db.execute("""
                SELECT id, snapshot_data FROM trading_state_snapshots
                ORDER BY timestamp DESC LIMIT 1
            """)
            
            result = cursor.fetchone()
            if not result:
                logger.info("No state snapshot found in database")
                return False
            
            snapshot_id, snapshot_data_json = result
            snapshot_data = json.loads(snapshot_data_json)
            
            # Restore main state
            self.state._cash = Decimal(str(snapshot_data["cash"]))
            self.state._equity = Decimal(str(snapshot_data["equity"]))
            self.state._peak_equity = Decimal(str(snapshot_data["peak_equity"]))
            self.state._drawdown = Decimal(str(snapshot_data["drawdown"]))
            self.state._trading_enabled = snapshot_data["trading_enabled"]
            self.state._daily_pnl = Decimal(str(snapshot_data["daily_pnl"]))
            self.state._trades_today = snapshot_data["trades_today"]
            
            # Restore positions
            cursor = self.db.execute("""
                SELECT symbol, side, quantity, entry_price, entry_time,
                       stop_loss, take_profit, unrealized_pnl, position_id
                FROM trading_state_positions
                WHERE snapshot_id = ?
            """, (snapshot_id,))
            
            for row in cursor.fetchall():
                symbol, side, qty, entry_price, entry_time_str, sl, tp, unrealized_pnl, pos_id = row
                entry_time = datetime.fromisoformat(entry_time_str)
                
                position = Position(
                    symbol=symbol,
                    side=side,
                    quantity=Decimal(str(qty)),
                    entry_price=Decimal(str(entry_price)),
                    entry_time=entry_time,
                    stop_loss=Decimal(str(sl)),
                    take_profit=Decimal(str(tp)),
                    unrealized_pnl=Decimal(str(unrealized_pnl)),
                    position_id=pos_id if pos_id else None,
                )
                
                self.state._open_positions[symbol] = position
            
            # Restore orders
            cursor = self.db.execute("""
                SELECT client_order_id, exchange_order_id, symbol, side, quantity,
                       price, order_type, time_in_force, status, created_at
                FROM trading_state_orders
                WHERE snapshot_id = ?
            """, (snapshot_id,))
            
            for row in cursor.fetchall():
                client_order_id, exchange_order_id, symbol, side, qty, price, order_type, tif, status, created_at_str = row
                created_at = datetime.fromisoformat(created_at_str)
                
                order = Order(
                    client_order_id=client_order_id,
                    exchange_order_id=exchange_order_id if exchange_order_id else None,
                    symbol=symbol,
                    side=side,
                    quantity=Decimal(str(qty)),
                    price=Decimal(str(price)),
                    order_type=order_type,
                    time_in_force=tif,
                    status=status,
                    created_at=created_at,
                )
                
                self.state._open_orders[client_order_id] = order
            
            logger.info(f"State restored from database (snapshot_id={snapshot_id})")
            return True
        
        except Exception as e:
            logger.error(f"Error restoring state: {e}", exc_info=True)
            return False
    
    def cleanup_old_snapshots(self, keep_last_n: int = 100) -> None:
        """
        Clean up old snapshots, keeping only the last N.
        
        Args:
            keep_last_n: Number of snapshots to keep
        """
        try:
            # Get IDs to delete
            cursor = self.db.execute("""
                SELECT id FROM trading_state_snapshots
                ORDER BY timestamp DESC
                LIMIT -1 OFFSET ?
            """, (keep_last_n,))
            
            ids_to_delete = [row[0] for row in cursor.fetchall()]
            
            if ids_to_delete:
                placeholders = ",".join("?" * len(ids_to_delete))
                self.db.execute(f"DELETE FROM trading_state_snapshots WHERE id IN ({placeholders})", ids_to_delete)
                self.db.commit()
                logger.info(f"Cleaned up {len(ids_to_delete)} old state snapshots")
        
        except Exception as e:
            logger.error(f"Error cleaning up snapshots: {e}", exc_info=True)

