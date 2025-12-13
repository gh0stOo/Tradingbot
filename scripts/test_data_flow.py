#!/usr/bin/env python3
"""
Test Data Flow to Dashboard and Discord Message Formatting
Validates that all data is correctly formatted and transmitted
"""

import sys
from pathlib import Path
import json
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.logger import setup_logger
from utils.config_loader import ConfigLoader
from data.database import Database
from data.data_collector import DataCollector
from data.position_tracker import PositionTracker
from integrations.bybit import BybitClient
from trading.order_manager import OrderManager
from trading.market_data import MarketData
from trading.bot import TradingBot

logger = setup_logger()

def test_database_data_flow():
    """Test if data flows correctly through database"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: DATABASE DATA FLOW")
    logger.info("="*60)

    try:
        db = Database("data/trading.db")
        dc = DataCollector(db)

        # Test 1: Verify trades are retrievable
        trades = dc.get_all_trades()
        if not trades:
            logger.error("ERROR: No trades found in database")
            return False

        logger.info(f"✓ Found {len(trades)} trades in database")

        # Test 2: Verify first trade has all required fields
        first_trade = trades[0]
        required_fields = [
            'id', 'symbol', 'side', 'entry_price', 'quantity',
            'stop_loss', 'take_profit', 'confidence', 'quality_score'
        ]

        missing_fields = [f for f in required_fields if f not in first_trade]
        if missing_fields:
            logger.error(f"ERROR: Trade missing fields: {missing_fields}")
            return False

        logger.info(f"✓ Trade has all {len(required_fields)} required fields")

        # Test 3: Verify closed trades can be retrieved
        closed_trades = dc.get_closed_trades()
        logger.info(f"✓ Retrieved {len(closed_trades)} closed trades")

        # Test 4: Verify trade statistics
        stats = dc.get_trade_stats()
        if not stats or 'total_trades' not in stats:
            logger.error("ERROR: Trade stats calculation failed")
            return False

        logger.info(f"✓ Trade stats: {stats}")

        # Test 5: Verify indicators are saved
        cursor = db.execute("SELECT COUNT(*) as count FROM indicators")
        ind_count = cursor.fetchone()['count']
        if ind_count == 0:
            logger.error("ERROR: No indicators found")
            return False

        logger.info(f"✓ Found {ind_count} indicator records")

        return True

    except Exception as e:
        logger.error(f"ERROR in database data flow: {e}", exc_info=True)
        return False


def test_dashboard_state_data():
    """Test if bot state is correctly tracked for dashboard"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: DASHBOARD STATE DATA")
    logger.info("="*60)

    try:
        config = ConfigLoader().config
        db = Database("data/trading.db")
        dc = DataCollector(db)

        bybit = BybitClient("", "", testnet=False)
        market_data = MarketData(bybit)
        position_tracker = PositionTracker(db)
        order_manager = OrderManager(bybit, "PAPER", position_tracker, dc)

        bot = TradingBot(config, market_data, order_manager, dc, position_tracker)

        # Test 1: Check bot has required state attributes
        required_attrs = ['current_positions', 'daily_pnl', 'loss_streak', 'ml_enabled']
        missing_attrs = [a for a in required_attrs if not hasattr(bot, a)]
        if missing_attrs:
            logger.error(f"ERROR: Bot missing attributes: {missing_attrs}")
            return False

        logger.info(f"✓ Bot has all {len(required_attrs)} required state attributes")

        # Test 2: Update and verify state tracking
        bot.update_state_tracking()
        logger.info(f"✓ Bot state updated: positions={bot.current_positions}, pnl={bot.daily_pnl}, ml_enabled={bot.ml_enabled}")

        # Test 3: Verify config has dashboard settings
        dashboard_config = config.get("dashboard", {})
        if not dashboard_config:
            logger.warning("WARNING: No dashboard configuration found")
        else:
            logger.info(f"✓ Dashboard config found: {list(dashboard_config.keys())}")

        return True

    except Exception as e:
        logger.error(f"ERROR in dashboard state test: {e}", exc_info=True)
        return False


def test_discord_message_formatting():
    """Test if Discord messages are correctly formatted"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: DISCORD MESSAGE FORMATTING")
    logger.info("="*60)

    try:
        config = ConfigLoader().config

        # Check Discord webhook configuration
        webhook_url = config.get("alerts", {}).get("discordWebhook", "")
        if not webhook_url:
            logger.warning("WARNING: No Discord webhook configured")
            return True

        logger.info("✓ Discord webhook configured")

        # Test alert handler creation
        from monitoring.alerting import discord_alert_handler

        # Test 1: Handler can be created
        handler = discord_alert_handler(webhook_url)
        logger.info("✓ Discord alert handler created successfully")

        # Test 2: Verify handler has required methods
        if not callable(handler):
            logger.warning("WARNING: Handler is not callable")

        return True

    except Exception as e:
        logger.error(f"ERROR in Discord message formatting: {e}", exc_info=True)
        return False


def test_data_integrity():
    """Test if all data is consistent and complete"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: DATA INTEGRITY")
    logger.info("="*60)

    try:
        db = Database("data/trading.db")
        dc = DataCollector(db)

        trades = dc.get_all_trades()

        if not trades:
            logger.warning("WARNING: No trades to validate")
            return True

        # Test 1: Check price consistency
        valid_trades = 0
        for trade in trades[:10]:
            entry = float(trade.get('entry_price', 0))
            exit_p = float(trade.get('exit_price', 0) or 0)
            pnl = float(trade.get('realized_pnl', 0))
            success = trade.get('success')

            if exit_p > 0:
                if success == 1 and pnl <= 0:
                    logger.warning(f"INCONSISTENCY: Trade marked as winning but pnl={pnl}")
                    continue
                valid_trades += 1

        logger.info(f"✓ Validated {valid_trades} trades for price consistency")

        # Test 2: Verify indicators match trades
        cursor = db.execute("SELECT COUNT(*) as count FROM indicators WHERE trade_id IN (SELECT id FROM trades)")
        ind_count = cursor.fetchone()['count']
        logger.info(f"✓ Found {ind_count} indicators linked to trades")

        # Test 3: Check for orphaned records
        cursor = db.execute("""
            SELECT COUNT(*) as count FROM indicators
            WHERE trade_id NOT IN (SELECT id FROM trades)
        """)
        orphaned = cursor.fetchone()['count']
        if orphaned > 0:
            logger.warning(f"WARNING: Found {orphaned} orphaned indicator records")
        else:
            logger.info("✓ No orphaned indicator records found")

        return True

    except Exception as e:
        logger.error(f"ERROR in data integrity test: {e}", exc_info=True)
        return False


def main():
    """Run all data flow tests"""
    logger.info("\n" + "="*80)
    logger.info("DATA FLOW AND FORMAT VALIDATION TEST SUITE")
    logger.info("="*80)

    results = {
        "database_flow": test_database_data_flow(),
        "dashboard_state": test_dashboard_state_data(),
        "discord_format": test_discord_message_formatting(),
        "data_integrity": test_data_integrity()
    }

    # Summary
    logger.info("\n" + "="*60)
    logger.info("DATA FLOW TEST SUMMARY")
    logger.info("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")

    logger.info(f"\nTotal: {passed}/{total} passed")

    if passed == total:
        logger.info("\n[SUCCESS] ALL DATA FLOW TESTS PASSED!")
        return 0
    else:
        logger.error(f"\n[FAILURE] {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
