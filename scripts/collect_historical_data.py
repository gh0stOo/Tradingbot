"""
Historical Data Collection Script

Downloads historical klines from Bybit and simulates the trading bot
to fill the database with backtesting data.
"""

import sys
from pathlib import Path
import time
from datetime import datetime, timedelta
import json
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.config_loader import ConfigLoader
from utils.logger import setup_logger
from integrations.bybit import BybitClient
from trading.market_data import MarketData
from trading.bot import TradingBot
from trading.order_manager import OrderManager
from data.database import Database
from data.data_collector import DataCollector
from data.position_tracker import PositionTracker


class HistoricalDataCollector:
    """Collects historical data and simulates trading"""

    def __init__(self, config: dict, logger: logging.Logger):
        """
        Initialize Historical Data Collector

        Args:
            config: Configuration dictionary
            logger: Logger instance
        """
        self.config = config
        self.logger = logger

        # Initialize components
        testnet = config.get("bybit", {}).get("testnet", False)
        self.bybit_client = BybitClient("", "", testnet)
        self.market_data = MarketData(self.bybit_client)

        # Initialize database
        db_path = config.get("ml", {}).get("database", {}).get("path", "data/trading.db")
        self.db = Database(db_path)
        self.data_collector = DataCollector(self.db)
        self.position_tracker = PositionTracker(self.db)

        # Initialize bot
        self.order_manager = OrderManager(None, "PAPER", self.position_tracker, self.data_collector)
        self.bot = TradingBot(
            config,
            self.market_data,
            self.order_manager,
            self.data_collector,
            self.position_tracker
        )

        self.logger.info("HistoricalDataCollector initialized")

    def get_historical_klines(
        self,
        symbol: str,
        interval: str = "1",
        days: int = 90,
        limit: int = 1000
    ) -> list:
        """
        Get historical klines from Bybit

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            interval: Kline interval (1, 5, 15, 60, etc.)
            days: Number of days to fetch
            limit: Limit per request (max 1000)

        Returns:
            List of kline data
        """
        self.logger.info(f"Fetching {days} days of {interval}min klines for {symbol}")

        all_klines = []
        end_time = int(datetime.utcnow().timestamp() * 1000)
        start_time = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)

        current_time = start_time

        while current_time < end_time:
            try:
                # Fetch klines
                klines_raw = self.bybit_client.get_klines(
                    symbol=symbol,
                    interval=interval,
                    startTime=current_time,
                    limit=limit
                )

                if not klines_raw:
                    self.logger.warning(f"No klines returned for {symbol} at {current_time}")
                    break

                # Convert to standard format (Bybit returns list of lists)
                for kline in klines_raw:
                    if isinstance(kline, list) and len(kline) >= 6:
                        all_klines.append({
                            "timestamp": datetime.fromtimestamp(int(kline[0]) / 1000),
                            "open": float(kline[1]),
                            "high": float(kline[2]),
                            "low": float(kline[3]),
                            "close": float(kline[4]),
                            "volume": float(kline[5])
                        })
                        # Update current_time for next batch
                        current_time = int(kline[0]) + (int(interval) * 60 * 1000)
                    else:
                        self.logger.warning(f"Unexpected kline format: {kline}")
                
                # If no new data, break
                if not klines_raw:
                    break

                # Rate limiting
                time.sleep(0.2)

                if len(all_klines) % 5000 == 0:
                    self.logger.info(f"Fetched {len(all_klines)} klines for {symbol}")

            except Exception as e:
                self.logger.error(f"Error fetching klines: {e}")
                break

        self.logger.info(f"Total klines fetched for {symbol}: {len(all_klines)}")
        return all_klines

    def get_top_coins(self, top_n: int = 10) -> list:
        """
        Get top coins by volume

        Args:
            top_n: Number of top coins

        Returns:
            List of symbols
        """
        self.logger.info(f"Fetching top {top_n} coins")

        try:
            symbols = self.market_data.get_top_coins(
                topN=top_n,
                minVolume=self.config.get("universe", {}).get("minVolume24h", 5000000)
            )

            if symbols:
                self.logger.info(f"Found {len(symbols)} symbols to backtest")
                for symbol in symbols[:5]:  # Log first 5
                    self.logger.info(f"  - {symbol}")
                return symbols
            else:
                self.logger.warning("No symbols found")
                return []
        except Exception as e:
            self.logger.error(f"Error fetching top coins: {e}")
            return []

    def simulate_trading(
        self,
        symbol: str,
        klines: list,
        batch_size: int = 100
    ) -> int:
        """
        Simulate trading on historical klines

        Args:
            symbol: Trading symbol
            klines: List of kline data
            batch_size: Number of klines to process at once

        Returns:
            Number of trades generated
        """
        self.logger.info(f"Simulating trading for {symbol} with {len(klines)} klines")

        trades_generated = 0
        errors = 0

        for i in range(0, len(klines) - batch_size, batch_size):
            try:
                # Get batch of klines
                batch = klines[i:i + batch_size]

                # Get symbol info
                symbol_info = self.market_data.get_symbol_info(symbol)
                if not symbol_info:
                    self.logger.warning(f"No symbol info for {symbol}")
                    break

                # Get BTC price (approximate)
                btc_price = 50000  # Default

                # Get equity
                equity = self.config.get("risk", {}).get("paperEquity", 10000)

                # Process symbol (this will generate signals and execute trades)
                result = self.bot.process_symbol(symbol, symbol_info, btc_price, equity)

                if result and result.get("execution", {}).get("success"):
                    trades_generated += 1

                # Progress logging
                if (i // batch_size) % 10 == 0:
                    self.logger.info(
                        f"Processed {i}/{len(klines)} klines, "
                        f"Generated {trades_generated} trades"
                    )

            except Exception as e:
                errors += 1
                self.logger.debug(f"Error processing batch: {e}")
                if errors > 10:
                    self.logger.warning("Too many errors, stopping simulation")
                    break

        self.logger.info(
            f"Simulation complete for {symbol}: "
            f"Generated {trades_generated} trades from {len(klines)} klines"
        )
        return trades_generated

    def collect_data(
        self,
        days: int = 90,
        top_n: int = 10,
        interval: str = "1"
    ):
        """
        Main method to collect historical data

        Args:
            days: Days of history to fetch
            top_n: Number of top coins
            interval: Kline interval (1=1min, 5=5min, 15=15min)
        """
        self.logger.info("=" * 60)
        self.logger.info("HISTORICAL DATA COLLECTION STARTED")
        self.logger.info(f"Configuration: {days} days, Top {top_n} coins, {interval}min interval")
        self.logger.info("=" * 60)

        start_time = time.time()
        total_trades = 0
        total_coins = 0

        try:
            # Get top coins
            symbols = self.get_top_coins(top_n)

            if not symbols:
                self.logger.error("No symbols found, aborting")
                return

            # Process each symbol
            for symbol in symbols[:3]:  # Limit to 3 for testing
                self.logger.info(f"\n--- Processing {symbol} ---")

                try:
                    # Get historical klines
                    klines = self.get_historical_klines(symbol, interval, days)

                    if not klines:
                        self.logger.warning(f"No klines for {symbol}, skipping")
                        continue

                    # Simulate trading
                    trades = self.simulate_trading(symbol, klines)
                    total_trades += trades
                    total_coins += 1

                except Exception as e:
                    self.logger.error(f"Error processing {symbol}: {e}")
                    continue

            # Print summary
            elapsed = time.time() - start_time
            self.logger.info("\n" + "=" * 60)
            self.logger.info("HISTORICAL DATA COLLECTION COMPLETE")
            self.logger.info(f"Total coins processed: {total_coins}")
            self.logger.info(f"Total trades generated: {total_trades}")
            self.logger.info(f"Time elapsed: {elapsed:.2f} seconds")
            self.logger.info("=" * 60)

            # Show statistics
            stats = self.data_collector.get_trade_stats()
            self.logger.info("\nTrade Statistics:")
            for key, value in stats.items():
                self.logger.info(f"  {key}: {value}")

        except Exception as e:
            self.logger.error(f"Fatal error: {e}")
            raise
        finally:
            self.db.close()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Collect historical market data")
    parser.add_argument("--days", type=int, default=30, help="Number of days to fetch (default: 30)")
    parser.add_argument("--top-n", type=int, default=1, help="Number of top coins (default: 1)")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Specific symbol to fetch (default: BTCUSDT)")
    parser.add_argument("--interval", type=str, default="1", help="Kline interval (default: 1)")
    
    args = parser.parse_args()
    
    logger = setup_logger()

    try:
        # Load config
        config_loader = ConfigLoader()
        config = config_loader.config
        logger.info("Config loaded successfully")

        # Create collector
        collector = HistoricalDataCollector(config, logger)

        # If specific symbol provided, fetch only that
        if args.symbol:
            logger.info(f"Fetching data for specific symbol: {args.symbol}")
            klines = collector.get_historical_klines(args.symbol, args.interval, args.days)
            if klines:
                # Save klines to database
                collector.data_collector.save_klines(args.symbol, klines)
                logger.info(f"Saved {len(klines)} klines for {args.symbol}")
        else:
            # Collect data for top coins
            collector.collect_data(
                days=args.days,
                top_n=args.top_n,
                interval=args.interval
            )

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
