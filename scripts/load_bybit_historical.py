#!/usr/bin/env python3
"""Einfaches Script zum Laden historischer Daten von Bybit API"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from integrations.bybit import BybitClient
from data.database import Database
from utils.config_loader import ConfigLoader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_historical_data(symbol: str = "BTCUSDT", days: int = 30):
    """
    Lade historische Daten von Bybit API und speichere in klines_archive
    
    Args:
        symbol: Trading-Paar (z.B. "BTCUSDT")
        days: Anzahl Tage zurück
    """
    logger.info(f"Loading {days} days of historical data for {symbol} from Bybit API")
    
    # Initialize components
    config_loader = ConfigLoader()
    config = config_loader.config
    
    # Get Bybit credentials
    bybit_config = config.get("bybit", {})
    api_key = os.getenv("BYBIT_API_KEY") or bybit_config.get("apiKey", "")
    api_secret = os.getenv("BYBIT_API_SECRET") or bybit_config.get("apiSecret", "")
    testnet = bybit_config.get("testnet", False)
    
    # Initialize Bybit client (public endpoints don't need auth, but we'll use it if available)
    bybit = BybitClient(api_key=api_key, api_secret=api_secret, testnet=testnet)
    
    # Initialize database
    db = Database()
    
    logger.info(f"Fetching klines from Bybit API...")
    
    # Bybit API returns latest klines, we need to fetch in batches
    # Each request returns up to 200 klines
    # For 30 days with 1-minute intervals: 30 * 24 * 60 = 43,200 klines
    # We need: 43,200 / 200 = 216 requests
    
    all_klines = []
    total_requests = 0
    max_requests = (days * 24 * 60) // 200 + 10  # Safety margin
    
    try:
        # Fetch klines in batches
        for i in range(max_requests):
            try:
                # Fetch latest klines (200 at a time)
                klines_raw = bybit.get_klines(
                    symbol=symbol,
                    category="linear",
                    interval=1,  # 1 minute
                    limit=200
                )
                
                if not klines_raw:
                    logger.warning(f"No more klines returned (request {i+1})")
                    break
                
                # Convert to standard format
                batch_count = 0
                for kline in klines_raw:
                    if isinstance(kline, list) and len(kline) >= 6:
                        try:
                            timestamp_ms = int(kline[0])
                            timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
                            
                            # Check if we're within date range
                            days_ago = (datetime.now() - timestamp).days
                            if days_ago > days:
                                # We've gone back far enough
                                logger.info(f"Reached {days_ago} days ago, stopping")
                                break
                            
                            kline_data = {
                                "timestamp": timestamp.isoformat(),
                                "open": float(kline[1]),
                                "high": float(kline[2]),
                                "low": float(kline[3]),
                                "close": float(kline[4]),
                                "volume": float(kline[5])
                            }
                            
                            # Store in database
                            db.execute(
                                """INSERT OR IGNORE INTO klines_archive 
                                   (symbol, timestamp, open, high, low, close, volume)
                                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    symbol,
                                    kline_data["timestamp"],
                                    kline_data["open"],
                                    kline_data["high"],
                                    kline_data["low"],
                                    kline_data["close"],
                                    kline_data["volume"]
                                )
                            )
                            all_klines.append(kline_data)
                            batch_count += 1
                            
                        except (ValueError, IndexError) as e:
                            logger.debug(f"Error parsing kline: {e}")
                            continue
                
                total_requests += 1
                
                if batch_count == 0:
                    logger.warning("No valid klines in batch, stopping")
                    break
                
                # Progress logging
                if total_requests % 10 == 0:
                    logger.info(f"Fetched {len(all_klines)} klines so far...")
                
                # Rate limiting (Bybit allows 120 requests/minute)
                time.sleep(0.5)
                
                # Flush writes periodically
                if total_requests % 50 == 0:
                    db.flush_writes(timeout=10.0)
                    logger.info(f"Flushed writes, total klines: {len(all_klines)}")
                
            except Exception as e:
                logger.error(f"Error fetching batch {i+1}: {e}")
                time.sleep(1)
                continue
        
        # Final flush
        db.flush_writes(timeout=30.0)
        logger.info(f"Final flush complete")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return False
    
    logger.info(f"Total klines fetched and saved: {len(all_klines)}")
    
    # Verify
    try:
        cursor = db.execute("SELECT COUNT(*) FROM klines_archive WHERE symbol = ?", (symbol,))
        count = cursor.fetchone()[0]
        logger.info(f"Total klines in database for {symbol}: {count}")
        
        # Get date range
        cursor = db.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM klines_archive WHERE symbol = ?",
            (symbol,)
        )
        row = cursor.fetchone()
        if row and row[0]:
            logger.info(f"Date range: {row[0]} to {row[1]}")
    except Exception as e:
        logger.warning(f"Error verifying data: {e}")
    
    return len(all_klines) > 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Load historical market data from Bybit API")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair (default: BTCUSDT)")
    parser.add_argument("--days", type=int, default=30, help="Number of days to load (default: 30)")
    
    args = parser.parse_args()
    
    success = load_historical_data(symbol=args.symbol, days=args.days)
    
    if success:
        print(f"\n✅ Successfully loaded {args.days} days of historical data for {args.symbol}")
        sys.exit(0)
    else:
        print(f"\n❌ Failed to load historical data")
        sys.exit(1)

