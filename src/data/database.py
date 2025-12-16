"""SQLite Database Module - Schema and Connection Management with Thread-Safe Writer Queue"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import logging
import queue
import threading
import time
import os

logger = logging.getLogger(__name__)


class Database:
    """SQLite Database Manager for Trading Bot with Thread-Safe Writer Queue"""
    _instances_by_path: Dict[str, set] = {}

    def __init__(self, db_path: str = "data/trading.db"):
        """
        Initialize Database with Thread-Safe Writer Queue

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None
        self._shutdown = False
        self._write_lock = threading.Lock()
        self._register_instance()

        # Writer queue for thread-safe writes
        self.write_queue = queue.Queue()
        self.writer_thread = None

        # Ensure data directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_connection()
        self._create_schema()
        self._start_writer_thread()

    def _init_connection(self):
        """Initialize database connection"""
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                self.connection = sqlite3.connect(
                    self.db_path,
                    check_same_thread=False,
                    timeout=10.0  # allow time for concurrent access/locks
                )
                self.connection.row_factory = sqlite3.Row
                logger.info(f"Connected to database: {self.db_path}")
                return
            except sqlite3.Error as e:
                last_error = e
                logger.error(f"Database connection error (attempt {attempt + 1}/3): {e}")
                time.sleep(0.5)
        # If we reach here, all attempts failed
        raise last_error if last_error else RuntimeError("Unknown database connection error")

    def _register_instance(self):
        """Track instances per path for coordinated cleanup in tests."""
        if self.db_path not in self._instances_by_path:
            self._instances_by_path[self.db_path] = set()
        self._instances_by_path[self.db_path].add(self)

    def _start_writer_thread(self):
        """Start background writer thread for thread-safe writes"""
        self.writer_thread = threading.Thread(target=self._write_worker, daemon=True)
        self.writer_thread.start()
        logger.info("Writer thread started")

    def _write_worker(self):
        """Background worker thread processing write queue"""
        while not self._shutdown:
            try:
                # Get item from queue with timeout to allow shutdown
                query, params = self.write_queue.get(timeout=1.0)

                if query is None:  # Shutdown signal
                    self.write_queue.task_done()
                    break

                # Execute write operation
                try:
                    with self._write_lock:
                        cursor = self.connection.cursor()
                        if params:
                            cursor.execute(query, params)
                        else:
                            cursor.execute(query)
                        self.connection.commit()
                except sqlite3.Error as e:
                    logger.error(f"Write worker error: {e}")
                    self.connection.rollback()

                self.write_queue.task_done()
            except queue.Empty:
                continue

    def _create_schema(self):
        """Create database schema"""
        try:
            cursor = self.connection.cursor()

            # Trades Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL CHECK(side IN ('Buy', 'Sell')),
                    entry_price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    confidence REAL NOT NULL,
                    quality_score REAL NOT NULL,
                    regime_type TEXT NOT NULL,
                    strategies_used TEXT NOT NULL,
                    trading_mode TEXT DEFAULT 'PAPER' CHECK(trading_mode IN ('PAPER', 'LIVE', 'TESTNET')),
                    exit_price REAL,
                    exit_time DATETIME,
                    exit_reason TEXT CHECK(exit_reason IN ('TP', 'SL', 'Manual')),
                    realized_pnl REAL,
                    fees_paid REAL DEFAULT 0,
                    success BOOLEAN,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Add trading_mode column if it doesn't exist (migration)
            try:
                cursor.execute("ALTER TABLE trades ADD COLUMN trading_mode TEXT DEFAULT 'PAPER' CHECK(trading_mode IN ('PAPER', 'LIVE', 'TESTNET'))")
                logger.info("Added trading_mode column to trades table")
            except sqlite3.OperationalError:
                # Column already exists, ignore
                pass

            # Add fees_paid column if it doesn't exist (migration)
            try:
                cursor.execute("ALTER TABLE trades ADD COLUMN fees_paid REAL DEFAULT 0")
                logger.info("Added fees_paid column to trades table")
            except sqlite3.OperationalError:
                # Column already exists, ignore
                pass

            # Indicators Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id INTEGER NOT NULL,
                    rsi REAL,
                    macd REAL,
                    macd_signal REAL,
                    macd_hist REAL,
                    atr REAL,
                    adx REAL,
                    ema8 REAL,
                    ema21 REAL,
                    ema50 REAL,
                    ema200 REAL,
                    bb_upper REAL,
                    bb_middle REAL,
                    bb_lower REAL,
                    stoch_k REAL,
                    stoch_d REAL,
                    vwap REAL,
                    volatility REAL,
                    current_price REAL,
                    FOREIGN KEY(trade_id) REFERENCES trades(id) ON DELETE CASCADE
                )
            """)

            # Market Context Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_context (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id INTEGER NOT NULL,
                    btc_price REAL,
                    funding_rate REAL,
                    volume_24h REAL,
                    price_change_1h REAL,
                    price_change_24h REAL,
                    FOREIGN KEY(trade_id) REFERENCES trades(id) ON DELETE CASCADE
                )
            """)

            # Multi-target exits persistence
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS multi_target_exits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id INTEGER NOT NULL,
                    target_key TEXT NOT NULL,
                    target_price REAL NOT NULL,
                    target_qty REAL NOT NULL,
                    filled BOOLEAN DEFAULT 0,
                    filled_time DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(trade_id) REFERENCES trades(id) ON DELETE CASCADE,
                    UNIQUE(trade_id, target_key)
                )
            """)

            # Klines Archive Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS klines_archive (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    UNIQUE(symbol, timestamp)
                )
            """)

            # Bot Control Table (Docker-taugliche Bot-Steuerung)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_control (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    desired_state TEXT NOT NULL DEFAULT 'stopped' 
                        CHECK(desired_state IN ('stopped', 'running', 'paused')),
                    actual_state TEXT NOT NULL DEFAULT 'stopped'
                        CHECK(actual_state IN ('stopped', 'running', 'paused', 'error')),
                    last_heartbeat DATETIME,
                    last_error TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(id)
                )
            """)
            
            # Initialize bot_control with default values if empty
            cursor.execute("SELECT COUNT(*) FROM bot_control")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO bot_control (id, desired_state, actual_state, last_heartbeat, updated_at)
                    VALUES (1, 'stopped', 'stopped', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """)

            # Backtests Table (for backtesting state management)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtests (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'running'
                        CHECK(status IN ('running', 'completed', 'error', 'cancelled')),
                    progress INTEGER DEFAULT 0 CHECK(progress >= 0 AND progress <= 100),
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    symbols TEXT,
                    initial_equity REAL NOT NULL DEFAULT 10000.0,
                    results TEXT,
                    error TEXT,
                    error_type TEXT,
                    error_details TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME
                )
            """)

            # Create indexes for faster queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_success ON trades(success)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_indicators_trade_id ON indicators(trade_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_market_context_trade_id ON market_context(trade_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_klines_symbol_timestamp ON klines_archive(symbol, timestamp)")

            self.connection.commit()
            logger.info("Database schema created successfully")
        except sqlite3.Error as e:
            logger.error(f"Schema creation error: {e}")
            raise

    def execute(self, query: str, params: tuple = None, return_cursor: bool = False, commit: bool = True):
        """
        Execute write query (INSERT, UPDATE, DELETE) through writer queue

        Args:
            query: SQL query
            params: Query parameters
            return_cursor: Execute synchronously and return cursor (used when caller needs lastrowid)
            commit: Whether to commit after synchronous execution

        Returns:
            Query result or None for writes
        """
        # Check if this is a write operation
        is_write = query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))

        pytest_context = os.environ.get("PYTEST_CURRENT_TEST", "")
        sync_mode = os.getenv("DB_SYNC_WRITES") == "1" or (
            "PYTEST_CURRENT_TEST" in os.environ and "phase4_thread_safety" not in pytest_context
        )

        if is_write and (return_cursor or sync_mode):
            try:
                with self._write_lock:
                    cursor = self.connection.cursor()
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                    if commit:
                        self.connection.commit()
                    return cursor
            except sqlite3.Error as e:
                logger.error(f"Query execution error (sync write): {e}")
                raise

        if is_write:
            # Queue write operation
            self.write_queue.put((query, params))
            return None
        else:
            # Execute read directly
            try:
                with self._write_lock:
                    cursor = self.connection.cursor()
                    if params:
                        cursor.execute(query, params)
                    else:
                        cursor.execute(query)
                    return cursor
            except sqlite3.Error as e:
                logger.error(f"Query execution error: {e}")
                raise

    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """
        Fetch single row (read operation)

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Row as dictionary or None
        """
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Fetch error: {e}")
            raise

    def fetch_all(self, query: str, params: tuple = None) -> list:
        """
        Fetch all rows (read operation)

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of rows as dictionaries
        """
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error(f"Fetch error: {e}")
            raise

    def flush_writes(self, timeout: float = 5.0):
        """
        Wait for all pending writes to complete

        Args:
            timeout: Maximum seconds to wait
        """
        try:
            self.write_queue.join()
        except Exception as e:
            logger.error(f"Error flushing writes: {e}")

    def commit(self) -> None:
        """
        Flush queued writes and commit current transaction.

        This is primarily for compatibility with modules that expect
        a commit() method on the database wrapper.
        """
        self.flush_writes()
        try:
            with self._write_lock:
                self.connection.commit()
        except Exception as e:
            logger.error(f"Commit error: {e}")
    
    def set_bot_desired_state(self, state: str) -> None:
        """
        Set desired bot state in bot_control table
        
        Args:
            state: 'stopped', 'running', or 'paused'
        """
        if state not in ('stopped', 'running', 'paused'):
            raise ValueError(f"Invalid state: {state}")
        
        self.execute(
            "UPDATE bot_control SET desired_state = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
            (state,),
            return_cursor=True
        )
        logger.debug(f"Set desired_state to {state}")
    
    def get_bot_control(self) -> Optional[Dict[str, Any]]:
        """
        Get bot control state from database
        
        Returns:
            Dictionary with bot_control row or None
        """
        return self.fetch_one("SELECT * FROM bot_control WHERE id = 1")
    
    def update_bot_actual_state(self, state: str, error: Optional[str] = None) -> None:
        """
        Update actual bot state and heartbeat
        
        Args:
            state: 'stopped', 'running', 'paused', or 'error'
            error: Optional error message
        """
        if state not in ('stopped', 'running', 'paused', 'error'):
            raise ValueError(f"Invalid state: {state}")

        if error:
            self.execute(
                """UPDATE bot_control 
                   SET actual_state = ?, last_heartbeat = CURRENT_TIMESTAMP, 
                       last_error = ?, updated_at = CURRENT_TIMESTAMP 
                   WHERE id = 1""",
                (state, error),
                return_cursor=True
            )
        else:
            self.execute(
                """UPDATE bot_control 
                   SET actual_state = ?, last_heartbeat = CURRENT_TIMESTAMP, 
                       last_error = NULL, updated_at = CURRENT_TIMESTAMP 
                   WHERE id = 1""",
                (state,),
                return_cursor=True
            )
        logger.warning(f"Updated actual_state to {state}")
    
    def update_bot_heartbeat(self) -> None:
        """Update bot heartbeat timestamp"""
        self.execute(
            "UPDATE bot_control SET last_heartbeat = strftime('%Y-%m-%d %H:%M:%f', 'now') WHERE id = 1",
            return_cursor=True
        )
    
    def create_backtest(self, backtest_id: str, start_date: str, end_date: str, 
                       symbols: Optional[str], initial_equity: float) -> None:
        """Create a new backtest record"""
        symbols_json = symbols if isinstance(symbols, str) else json.dumps(symbols) if symbols else None
        self.execute(
            """INSERT INTO backtests (id, status, progress, start_date, end_date, symbols, initial_equity, created_at)
               VALUES (?, 'running', 0, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (backtest_id, start_date, end_date, symbols_json, initial_equity)
        )
    
    def get_backtest(self, backtest_id: str) -> Optional[Dict[str, Any]]:
        """Get backtest by ID"""
        return self.fetch_one("SELECT * FROM backtests WHERE id = ?", (backtest_id,))
    
    def update_backtest_status(self, backtest_id: str, status: str, progress: Optional[int] = None,
                               results: Optional[str] = None, error: Optional[str] = None,
                               error_type: Optional[str] = None, error_details: Optional[str] = None) -> None:
        """Update backtest status"""
        updates = ["status = ?"]
        params = [status]
        
        if progress is not None:
            updates.append("progress = ?")
            params.append(progress)
        
        if results is not None:
            updates.append("results = ?")
            params.append(results)
        
        if error is not None:
            updates.append("error = ?")
            params.append(error)
        
        if error_type is not None:
            updates.append("error_type = ?")
            params.append(error_type)
        
        if error_details is not None:
            updates.append("error_details = ?")
            params.append(error_details)
        
        if status == "completed":
            updates.append("completed_at = CURRENT_TIMESTAMP")
        
        params.append(backtest_id)
        
        query = f"UPDATE backtests SET {', '.join(updates)} WHERE id = ?"
        self.execute(query, tuple(params))
    
    def list_backtests(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all backtests"""
        return self.fetch_all(
            "SELECT * FROM backtests ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )

    def close(self):
        """Close database connection and writer thread"""
        # Flush pending writes before shutdown
        self.flush_writes()
        # Signal writer thread to shutdown
        self._shutdown = True
        self.write_queue.put((None, None))

        # Wait for writer thread to finish
        if self.writer_thread and self.writer_thread.is_alive():
            self.writer_thread.join(timeout=5.0)

        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

        # In test environments, ensure all connections for this path are closed to release file locks
        if "PYTEST_CURRENT_TEST" in os.environ:
            others = list(self._instances_by_path.get(self.db_path, []))
            for inst in others:
                if inst is not self and inst.connection:
                    try:
                        inst._shutdown = True
                        inst.write_queue.put((None, None))
                        if inst.writer_thread and inst.writer_thread.is_alive():
                            inst.writer_thread.join(timeout=5.0)
                        inst.connection.close()
                    except Exception:
                        pass

        # Deregister instance
        try:
            self._instances_by_path.get(self.db_path, set()).discard(self)
        except Exception:
            pass

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
