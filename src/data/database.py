"""SQLite Database Module - Schema and Connection Management"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)


class Database:
    """SQLite Database Manager for Trading Bot"""

    def __init__(self, db_path: str = "data/trading.db"):
        """
        Initialize Database

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None

        # Ensure data directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_connection()
        self._create_schema()

    def _init_connection(self):
        """Initialize database connection"""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise

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
        Execute query

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Cursor object
        """
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            self.connection.commit()
            return cursor
        except sqlite3.Error as e:
            logger.error(f"Query execution error: {e}")
            self.connection.rollback()
            raise

    def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """
        Fetch single row

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
        Fetch all rows

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

    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
