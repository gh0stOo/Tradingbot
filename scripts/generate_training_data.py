#!/usr/bin/env python3
"""
Generate synthetic training data for ML models
Creates realistic trading data for backtesting without needing live API calls
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.database import Database
from utils.logger import setup_logger

logger = setup_logger()


def generate_synthetic_trades(n_trades=200):
    """Generate synthetic trade data for training"""
    logger.info(f"Generating {n_trades} synthetic trades...")
    
    trades_data = []
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOGEUSDT']
    
    start_time = datetime.utcnow() - timedelta(days=60)  # 60 days ago
    
    for i in range(n_trades):
        # Random symbol and timing
        symbol = np.random.choice(symbols)
        entry_time = start_time + timedelta(hours=i * 6 + np.random.randint(0, 120))
        exit_time = entry_time + timedelta(hours=np.random.randint(1, 12))
        
        # Random prices (realistic ranges)
        if symbol == 'BTCUSDT':
            entry_price = np.random.uniform(40000, 45000)
            exit_price = entry_price + np.random.normal(0, 500)
        elif symbol == 'ETHUSDT':
            entry_price = np.random.uniform(2000, 2500)
            exit_price = entry_price + np.random.normal(0, 50)
        else:
            entry_price = np.random.uniform(0.5, 5.0)
            exit_price = entry_price + np.random.normal(0, 0.1)
        
        # PnL calculation
        pnl = (exit_price - entry_price) * 100  # Assume 100 units
        
        # Random indicators (realistic ranges)
        indicators = {
            'rsi': np.random.uniform(20, 80),
            'macd': np.random.normal(0, 50),
            'macd_signal': np.random.normal(0, 50),
            'atr': abs(np.random.normal(100, 50)),
            'adx': np.random.uniform(10, 50),
            'ema_8': entry_price + np.random.normal(0, 10),
            'ema_21': entry_price + np.random.normal(0, 20),
            'ema_50': entry_price + np.random.normal(0, 50),
            'ema_200': entry_price + np.random.normal(0, 100),
        }
        
        trades_data.append({
            'trade_id': i + 1,
            'entry_time': entry_time.isoformat(),
            'exit_time': exit_time.isoformat(),
            'symbol': symbol,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'realized_pnl': pnl,
            'entry_reason': f'strategy_signal_{i % 5}',
            'success': 1 if pnl > 0 else 0,
            'indicators': indicators
        })
    
    logger.info(f"Generated {len(trades_data)} trades")
    logger.info(f"Win rate: {sum(1 for t in trades_data if t['success']) / len(trades_data) * 100:.1f}%")
    
    return trades_data


def insert_trades_to_db(db: Database, trades_data: list):
    """Insert trades and indicators into database"""
    logger.info("Inserting trades into database...")

    trade_count = 0
    for trade in trades_data:
        try:
            # Insert trade with proper schema columns
            db.execute(
                """INSERT INTO trades
                   (timestamp, symbol, side, entry_price, quantity, stop_loss, take_profit,
                    confidence, quality_score, regime_type, strategies_used,
                    exit_price, exit_time, exit_reason, realized_pnl, success, trading_mode)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trade['entry_time'],
                    trade['symbol'],
                    'Buy',  # Default to Buy
                    trade['entry_price'],
                    100,  # Default quantity
                    trade['entry_price'] * 0.98,  # Stop loss 2% below
                    trade['entry_price'] * 1.05,  # Take profit 5% above
                    0.6,  # Confidence
                    0.7,  # Quality score
                    'trending',  # Regime
                    trade['entry_reason'],
                    trade['exit_price'],
                    trade['exit_time'],
                    'TP' if trade['success'] else 'SL',
                    trade['realized_pnl'],
                    trade['success'],
                    'PAPER'  # Paper trading mode
                )
            )

            # Get the last inserted row ID
            cursor = db.connection.cursor()
            cursor.execute("SELECT last_insert_rowid()")
            trade_id = cursor.fetchone()[0]

            # Insert indicators
            ind = trade['indicators']
            db.execute(
                """INSERT INTO indicators
                   (trade_id, rsi, macd, macd_signal, atr, adx, ema8, ema21, ema50, ema200, volatility)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trade_id,
                    ind['rsi'],
                    ind['macd'],
                    ind['macd_signal'],
                    ind['atr'],
                    ind['adx'],
                    ind['ema_8'],
                    ind['ema_21'],
                    ind['ema_50'],
                    ind['ema_200'],
                    0.02  # Default volatility
                )
            )

            trade_count += 1
            
        except Exception as e:
            logger.debug(f"Error inserting trade: {e}")
            continue

    logger.info(f"Inserted {trade_count} trades into database")


def main():
    """Main function"""
    logger.info("=" * 60)
    logger.info("SYNTHETIC TRAINING DATA GENERATION")
    logger.info("=" * 60)
    
    try:
        db = Database("data/trading.db")
        
        # Generate synthetic trades
        trades_data = generate_synthetic_trades(n_trades=200)
        
        # Insert into database
        insert_trades_to_db(db, trades_data)
        
        logger.info("=" * 60)
        logger.info("✅ Training data generated successfully!")
        logger.info("=" * 60)
        logger.info("Ready to train ML models")
        logger.info("Run: python scripts/train_models.py")
        
        return 0
        
    except Exception as e:
        logger.error(f"Failed to generate training data: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
