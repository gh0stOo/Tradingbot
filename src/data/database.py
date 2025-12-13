"""SQLite Database Module - Schema and Connection Management with Thread-Safe Writer Queue"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
import json
import logging
import queue
import threading
import time

logger = logging.getLogger(__name__)


class Database:
    """SQLite Database Manager for Trading Bot with Thread-Safe Writer Queue"""

    def __init__(self, db_path: str = "data/trading.db"):
        """
        Initialize Database with Thread-Safe Writer Queue

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None
        self._shutdown = False

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
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise

    def _start_writer_thread(self):
        """Start background writer thread for thread-safe writes"""
        self.writer_thread = threading.Thread(target=self._write_worker, daemon=False)
        self.writer_thread.start()
        logger.info("Writer thread started")

    def _write_worker(self):
        """Background worker thread processing write queue"""
        while not self._shutdown:
            try:
                # Get item from queue with timeout to allow shutdown
                query, params = self.write_queue.get(timeout=1.0)

                if query is None:  # Shutdown signal
                    break

                # Execute write operation
                try:
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

    def execute(self, query: str, params: tuple = None):
        """
        Execute write query (INSERT, UPDATE, DELETE) through writer queue

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Query result or None for writes
        """
        # Check if this is a write operation
        is_write = query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE'))

        if is_write:
            # Queue write operation
            self.write_queue.put((query, params))
            return None
        else:
            # Execute read directly
            try:
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

    def close(self):
        """Close database connection and writer thread"""
        # Signal writer thread to shutdown
        self._shutdown = True
        self.write_queue.put((None, None))

        # Wait for writer thread to finish
        if self.writer_thread and self.writer_thread.is_alive():
            self.writer_thread.join(timeout=5.0)

        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
