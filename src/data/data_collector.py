"""Data Collector Module - Logging trades and indicators to database"""

from typing import Dict, Any, Optional, List
import json
from datetime import datetime
import logging

from data.database import Database

logger = logging.getLogger(__name__)


class DataCollector:
    """Collects and stores trading data to SQLite database"""

    def __init__(self, db: Database):
        """
        Initialize Data Collector

        Args:
            db: Database instance
        """
        self.db = db
        self.open_trades: Dict[str, int] = {}  # symbol -> trade_id mapping

    def save_trade_entry(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        stop_loss: float,
        take_profit: float,
        confidence: float,
        quality_score: float,
        regime_type: str,
        strategies_used: List[str],
        timestamp: Optional[datetime] = None,
        trading_mode: str = "PAPER"
    ) -> Optional[int]:
        """
        Save new trade entry

        Args:
            symbol: Trading symbol
            side: Buy or Sell
            entry_price: Entry price
            quantity: Trade quantity
            stop_loss: Stop loss price
            take_profit: Take profit price
            confidence: Signal confidence
            quality_score: Signal quality score
            regime_type: Market regime
            strategies_used: List of strategies that generated signal
            timestamp: Trade timestamp (default: now)

        Returns:
            Trade ID or None if failed
        """
        try:
            if not self.db:
                logger.error("Database connection not available")
                return None
                
            timestamp = timestamp or datetime.utcnow()
            strategies_json = json.dumps(strategies_used)

            cursor = self.db.execute("""
                INSERT INTO trades (
                    timestamp, symbol, side, entry_price, quantity,
                    stop_loss, take_profit, confidence, quality_score,
                    regime_type, strategies_used, trading_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, symbol, side, entry_price, quantity,
                stop_loss, take_profit, confidence, quality_score,
                regime_type, strategies_json, trading_mode
            ), return_cursor=True)

            if cursor is None:
                logger.error("Database execute returned None")
                return None

            trade_id = cursor.lastrowid
            self.open_trades[symbol] = trade_id

            logger.info(f"Trade entry saved: {symbol} {side} @ {entry_price} (Trade ID: {trade_id})")
            return trade_id
        except Exception as e:
            logger.error(f"Error saving trade entry: {e}")
            return None

    def save_indicators(
        self,
        trade_id: int,
        indicators: Dict[str, float],
        current_price: float
    ) -> bool:
        """
        Save indicators for trade

        Args:
            trade_id: Trade ID
            indicators: Dictionary of indicators
            current_price: Current price

        Returns:
            True if successful
        """
        try:
            cursor = self.db.execute("""
                INSERT INTO indicators (
                    trade_id, rsi, macd, macd_signal, macd_hist,
                    atr, adx, ema8, ema21, ema50, ema200,
                    bb_upper, bb_middle, bb_lower, stoch_k, stoch_d,
                    vwap, volatility, current_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                indicators.get("rsi"),
                indicators.get("macd"),
                indicators.get("macdSignal"),
                indicators.get("macdHist"),
                indicators.get("atr"),
                indicators.get("adx"),
                indicators.get("ema8"),
                indicators.get("ema21"),
                indicators.get("ema50"),
                indicators.get("ema200"),
                indicators.get("bbUpper"),
                indicators.get("bbMiddle"),
                indicators.get("bbLower"),
                indicators.get("stochK"),
                indicators.get("stochD"),
                indicators.get("vwap"),
                indicators.get("volatility"),
                current_price
            ))

            logger.debug(f"Indicators saved for trade {trade_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving indicators: {e}")
            return False

    def save_market_context(
        self,
        trade_id: int,
        btc_price: float,
        funding_rate: float = 0.0,
        volume_24h: float = 0.0,
        price_change_1h: float = 0.0,
        price_change_24h: float = 0.0
    ) -> bool:
        """
        Save market context for trade

        Args:
            trade_id: Trade ID
            btc_price: BTC price
            funding_rate: Funding rate
            volume_24h: 24h volume
            price_change_1h: 1h price change %
            price_change_24h: 24h price change %

        Returns:
            True if successful
        """
        try:
            self.db.execute("""
                INSERT INTO market_context (
                    trade_id, btc_price, funding_rate, volume_24h,
                    price_change_1h, price_change_24h
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                trade_id, btc_price, funding_rate, volume_24h,
                price_change_1h, price_change_24h
            ))

            logger.debug(f"Market context saved for trade {trade_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving market context: {e}")
            return False

    def save_klines(
        self,
        symbol: str,
        klines: List[Dict[str, Any]]
    ) -> bool:
        """
        Save klines to archive

        Args:
            symbol: Trading symbol
            klines: List of kline data

        Returns:
            True if successful
        """
        try:
            for kline in klines:
                try:
                    self.db.execute("""
                        INSERT OR IGNORE INTO klines_archive (
                            symbol, timestamp, open, high, low, close, volume
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol,
                        kline.get("timestamp"),
                        kline.get("open"),
                        kline.get("high"),
                        kline.get("low"),
                        kline.get("close"),
                        kline.get("volume")
                    ))
                except Exception as e:
                    logger.debug(f"Duplicate kline for {symbol}: {e}")
                    continue

            logger.debug(f"Saved {len(klines)} klines for {symbol}")
            return True
        except Exception as e:
            logger.error(f"Error saving klines: {e}")
            return False

    def get_open_trade(self, symbol: str) -> Optional[int]:
        """
        Get open trade ID for symbol

        Args:
            symbol: Trading symbol

        Returns:
            Trade ID or None
        """
        return self.open_trades.get(symbol)

    def get_recent_trades(self, symbol: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent trades for symbol

        Args:
            symbol: Trading symbol
            limit: Max number of trades

        Returns:
            List of trades
        """
        try:
            return self.db.fetch_all("""
                SELECT * FROM trades
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (symbol, limit))
        except Exception as e:
            logger.error(f"Error fetching recent trades: {e}")
            return []

    def get_trade_stats(self, symbol: str = None) -> Dict[str, Any]:
        """
        Get trade statistics

        Args:
            symbol: Filter by symbol (None for all)

        Returns:
            Statistics dictionary
        """
        try:
            if symbol:
                total = self.db.fetch_one(
                    "SELECT COUNT(*) as count FROM trades WHERE symbol = ?",
                    (symbol,)
                )
                closed = self.db.fetch_one(
                    "SELECT COUNT(*) as count FROM trades WHERE symbol = ? AND success IS NOT NULL",
                    (symbol,)
                )
                winning = self.db.fetch_one(
                    "SELECT COUNT(*) as count FROM trades WHERE symbol = ? AND success = 1",
                    (symbol,)
                )
            else:
                total = self.db.fetch_one("SELECT COUNT(*) as count FROM trades")
                closed = self.db.fetch_one("SELECT COUNT(*) as count FROM trades WHERE success IS NOT NULL")
                winning = self.db.fetch_one("SELECT COUNT(*) as count FROM trades WHERE success = 1")

            total_count = total.get("count", 0) if total else 0
            closed_count = closed.get("count", 0) if closed else 0
            winning_count = winning.get("count", 0) if winning else 0

            win_rate = (winning_count / closed_count * 100) if closed_count > 0 else 0

            return {
                "total_trades": total_count,
                "closed_trades": closed_count,
                "winning_trades": winning_count,
                "win_rate": round(win_rate, 2)
            }
        except Exception as e:
            logger.error(f"Error calculating trade stats: {e}")
            return {}

    def get_all_trades(self) -> List[Dict[str, Any]]:
        """
        Get all trades from database

        Returns:
            List of trade dictionaries
        """
        try:
            cursor = self.db.execute("""
                SELECT * FROM trades
                ORDER BY timestamp DESC
            """)

            trades = []
            for row in cursor.fetchall():
                trade = dict(row)
                # Parse strategies_used JSON if present
                strategies_raw = trade.get("strategies_used")
                if isinstance(strategies_raw, str):
                    strategies_raw = strategies_raw.strip()
                    if not strategies_raw:
                        trade["strategies_used"] = []
                    else:
                        try:
                            trade["strategies_used"] = json.loads(strategies_raw)
                        except (json.JSONDecodeError, ValueError) as parse_error:
                            logger.debug(f"Failed to parse strategies_used JSON: {parse_error}")
                            trade["strategies_used"] = []
                trades.append(trade)

            return trades
        except Exception as e:
            logger.error(f"Error getting all trades: {e}")
            return []

    def get_closed_trades(self) -> List[Dict[str, Any]]:
        """
        Get closed trades only

        Returns:
            List of closed trade dictionaries
        """
        try:
            cursor = self.db.execute("""
                SELECT * FROM trades
                WHERE exit_time IS NOT NULL
                ORDER BY exit_time DESC
            """)

            trades = []
            for row in cursor.fetchall():
                trade = dict(row)
                if 'strategies_used' in trade and isinstance(trade['strategies_used'], str):
                    try:
                        trade['strategies_used'] = json.loads(trade['strategies_used'])
                    except (json.JSONDecodeError, ValueError) as parse_error:
                        logger.warning(f"Failed to parse strategies_used JSON: {parse_error}")
                        trade['strategies_used'] = []
                trades.append(trade)

            return trades
        except Exception as e:
            logger.error(f"Error getting closed trades: {e}")
            return []
