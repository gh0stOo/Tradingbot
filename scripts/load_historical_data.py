#!/usr/bin/env python3
"""Script zum Laden historischer Marktdaten für Backtesting"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from integrations.bybit import BybitClient
from data.database import Database
from utils.config_loader import ConfigLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_historical_data(symbol: str = "BTCUSDT", days: int = 30):
    """
    Lade historische Daten von Bybit und speichere in klines_archive
    
    Args:
        symbol: Trading-Paar (z.B. "BTCUSDT")
        days: Anzahl Tage zurück
    """
    logger.info(f"Loading historical data for {symbol} ({days} days)")
    
    # Initialize components
    config_loader = ConfigLoader()
    config = config_loader.config
    
    # Get Bybit credentials
    bybit_config = config.get("bybit", {})
    api_key = os.getenv("BYBIT_API_KEY") or bybit_config.get("apiKey")
    api_secret = os.getenv("BYBIT_API_SECRET") or bybit_config.get("apiSecret")
    testnet = bybit_config.get("testnet", False)
    
    if not api_key or not api_secret:
        logger.error("Bybit API credentials not found. Set BYBIT_API_KEY and BYBIT_API_SECRET environment variables.")
        return False
    
    # Initialize Bybit client
    bybit = BybitClient(api_key=api_key, api_secret=api_secret, testnet=testnet)
    
    # Initialize database
    db = Database()
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    logger.info(f"Fetching klines from {start_date} to {end_date}")
    
    # Fetch klines from Bybit (1-minute intervals)
    # Bybit API limit: 200 klines per request
    # We need to fetch in batches
    all_klines = []
    current_start = start_date
    
    while current_start < end_date:
        # Calculate batch end (max 200 klines = ~200 minutes = ~3.3 hours)
        batch_end = min(current_start + timedelta(hours=3), end_date)
        
        try:
            # Fetch klines (Bybit API returns latest klines, we need to use start/end parameters)
            # Note: Bybit API v5 uses different parameters - adjust based on actual API
            klines = bybit.get_klines(
                symbol=symbol,
                category="linear",
                interval=1,  # 1 minute
                limit=200  # Max per request
            )
            
            if klines:
                all_klines.extend(klines)
                logger.info(f"Fetched {len(klines)} klines (total: {len(all_klines)})")
            else:
                logger.warning(f"No klines returned for batch {current_start} to {batch_end}")
            
            # Move to next batch
            current_start = batch_end
            
            # Rate limiting
            import time
            time.sleep(0.1)  # Small delay to avoid rate limits
            
        except Exception as e:
            logger.error(f"Error fetching klines for batch {current_start} to {batch_end}: {e}")
            current_start = batch_end
            continue
    
    if not all_klines:
        logger.error("No klines fetched. Check API credentials and network connection.")
        return False
    
    logger.info(f"Total klines fetched: {len(all_klines)}")
    
    # Store in database
    logger.info("Storing klines in database...")
    saved_count = 0
    
    for kline in all_klines:
        try:
            # Convert timestamp if needed
            timestamp = kline.get("timestamp")
            if isinstance(timestamp, str):
                # Parse ISO format
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            elif isinstance(timestamp, (int, float)):
                # Convert Unix timestamp
                timestamp = datetime.fromtimestamp(timestamp / 1000 if timestamp > 1e10 else timestamp)
            
            # Store in database
            db.execute(
                """INSERT OR IGNORE INTO klines_archive 
                   (symbol, timestamp, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    symbol,
                    timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
                    float(kline.get("open", 0)),
                    float(kline.get("high", 0)),
                    float(kline.get("low", 0)),
                    float(kline.get("close", 0)),
                    float(kline.get("volume", 0))
                )
            )
            saved_count += 1
            
        except Exception as e:
            logger.debug(f"Error saving kline: {e}")
            continue
    
    # Flush writes
    db.flush_writes(timeout=30.0)
    
    logger.info(f"Saved {saved_count} klines to database")
    
    # Verify
    cursor = db.execute("SELECT COUNT(*) FROM klines_archive WHERE symbol = ?", (symbol,))
    count = cursor.fetchone()[0]
    logger.info(f"Total klines in database for {symbol}: {count}")
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Load historical market data for backtesting")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair (default: BTCUSDT)")
    parser.add_argument("--days", type=int, default=30, help="Number of days to load (default: 30)")
    
    args = parser.parse_args()
    
    success = load_historical_data(symbol=args.symbol, days=args.days)
    
    if success:
        print(f"✅ Successfully loaded {args.days} days of historical data for {args.symbol}")
        sys.exit(0)
    else:
        print(f"❌ Failed to load historical data")
        sys.exit(1)

