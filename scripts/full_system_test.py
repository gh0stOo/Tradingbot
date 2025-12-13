#!/usr/bin/env python3
"""
Comprehensive System Test for Trading Bot
Tests all major components and integrations
"""

import sys
from pathlib import Path
from datetime import datetime
import json

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.logger import setup_logger
from utils.config_loader import ConfigLoader

logger = setup_logger()

# Test results tracking
test_results = {
    "timestamp": datetime.utcnow().isoformat(),
    "total_tests": 0,
    "passed": 0,
    "failed": 0,
    "errors": []
}

def log_test(name, passed, error=None):
    """Log a test result"""
    test_results["total_tests"] += 1
    if passed:
        test_results["passed"] += 1
        logger.info(f"[PASS] {name}")
    else:
        test_results["failed"] += 1
        logger.error(f"[FAIL] {name}: {error}")
        test_results["errors"].append({"test": name, "error": str(error)})

def main():
    """Main test suite"""

    logger.info("="*60)
    logger.info("COMPREHENSIVE BOT SYSTEM TEST")
    logger.info("="*60)

    # ==================== TEST 1: CONFIG LOADING ====================
    logger.info("\n[1] CONFIG LOADING")
    try:
        config_loader = ConfigLoader()
        config = config_loader.config
        required_keys = ["trading", "strategies", "risk", "ml", "bybit"]
        for key in required_keys:
            if key in config:
                log_test(f"Config key '{key}'", True)
            else:
                log_test(f"Config key '{key}'", False, f"Missing")
    except Exception as e:
        log_test("Config loading", False, str(e))
        return 1

    # ==================== TEST 2: DATABASE ====================
    logger.info("\n[2] DATABASE")
    try:
        from data.database import Database
        db = Database("data/trading.db")
        log_test("Database connection", True)

        cursor = db.execute("SELECT COUNT(*) FROM trades")
        trade_count = cursor.fetchone()[0]
        log_test(f"Trades table ({trade_count} trades)", True)

        cursor = db.execute("SELECT COUNT(*) FROM indicators")
        ind_count = cursor.fetchone()[0]
        log_test(f"Indicators table ({ind_count} records)", True)

    except Exception as e:
        log_test("Database", False, str(e))

    # ==================== TEST 3: DATA COLLECTOR ====================
    logger.info("\n[3] DATA COLLECTOR")
    try:
        from data.data_collector import DataCollector
        data_collector = DataCollector(db)
        log_test("DataCollector init", True)

        trades = data_collector.get_all_trades()
        log_test(f"Get trades ({len(trades)} returned)", True)

    except Exception as e:
        log_test("DataCollector", False, str(e))

    # ==================== TEST 4: MARKET DATA ====================
    logger.info("\n[4] MARKET DATA")
    try:
        from trading.market_data import MarketData
        from integrations.bybit import BybitClient

        bybit_client = BybitClient("", "", testnet=False)
        market_data = MarketData(bybit_client)
        log_test("MarketData init", True)

    except Exception as e:
        log_test("MarketData", False, str(e))

    # ==================== TEST 5: INDICATORS ====================
    logger.info("\n[5] INDICATORS")
    try:
        from trading.indicators import Indicators
        import pandas as pd
        import numpy as np

        indicators = Indicators()
        log_test("Indicators init", True)

        klines = pd.DataFrame({
            'close': np.random.uniform(40000, 45000, 100),
            'high': np.random.uniform(40000, 45000, 100),
            'low': np.random.uniform(40000, 45000, 100),
            'volume': np.random.uniform(1000, 10000, 100)
        })

        rsi = indicators.rsi(klines['close'], 14)
        log_test("RSI calculation", rsi is not None)

        macd = indicators.macd(klines['close'])
        log_test("MACD calculation", macd is not None)

    except Exception as e:
        log_test("Indicators", False, str(e))

    # ==================== TEST 6: STRATEGIES ====================
    logger.info("\n[6] STRATEGIES")
    try:
        from trading.strategies import Strategies
        strategies = Strategies(config)
        log_test("Strategies init", True)

    except Exception as e:
        log_test("Strategies", False, str(e))

    # ==================== TEST 7: RISK MANAGER ====================
    logger.info("\n[7] RISK MANAGER")
    try:
        from trading.risk_manager import RiskManager
        risk_manager = RiskManager(config)
        log_test("RiskManager init", True)

        kelly = risk_manager.calculate_kelly_fraction(0.55, 10, 5)
        log_test(f"Kelly calc (={kelly:.4f})", True)

    except Exception as e:
        log_test("RiskManager", False, str(e))

    # ==================== TEST 8: ML MODELS ====================
    logger.info("\n[8] ML MODELS")
    try:
        from ml.signal_predictor import SignalPredictor
        from ml.regime_classifier import RegimeClassifier

        sp = SignalPredictor()
        loaded_sp = sp.load()
        log_test("Signal Predictor loading", loaded_sp)

        rc = RegimeClassifier()
        loaded_rc = rc.load()
        log_test("Regime Classifier loading", loaded_rc)

    except Exception as e:
        log_test("ML Models", False, str(e))

    # ==================== TEST 9: BOT INITIALIZATION ====================
    logger.info("\n[9] BOT INITIALIZATION")
    try:
        from trading.bot import TradingBot
        from data.position_tracker import PositionTracker
        from trading.order_manager import OrderManager

        position_tracker = PositionTracker(db)
        order_manager = OrderManager(bybit_client, "PAPER", position_tracker, data_collector)

        bot = TradingBot(config, market_data, order_manager, data_collector, position_tracker)
        log_test("Bot init", True)
        log_test(f"ML enabled: {bot.ml_enabled}", True)

    except Exception as e:
        log_test("Bot", False, str(e))
        import traceback
        traceback.print_exc()

    # ==================== TEST 10: DASHBOARD STATE ====================
    logger.info("\n[10] DASHBOARD STATE MANAGER")
    try:
        from dashboard.bot_state_manager import BotStateManager, BotStatus

        state_manager = BotStateManager()
        log_test("BotStateManager init", True)

        state_manager.set_status(BotStatus.RUNNING)
        log_test("Set bot status", True)

    except Exception as e:
        log_test("BotStateManager", False, str(e))

    # ==================== TEST 11: DISCORD INTEGRATION ====================
    logger.info("\n[11] DISCORD INTEGRATION")
    try:
        from monitoring.alerting import discord_alert_handler

        webhook_url = config.get("alerts", {}).get("discordWebhook")
        if webhook_url and webhook_url != "":
            handler = discord_alert_handler(webhook_url)
            log_test("Discord handler creation", True)
        else:
            log_test("Discord webhook URL", False, "Not configured")

    except Exception as e:
        log_test("Discord integration", False, str(e))

    # ==================== TEST 12: API ROUTES ====================
    logger.info("\n[12] API ROUTES")
    try:
        from api.routes import router
        log_test("API routes import", True)

        from api.server import app
        log_test("FastAPI app", True)

    except Exception as e:
        log_test("API Routes", False, str(e))

    # ==================== FINAL REPORT ====================
    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)

    logger.info(f"Total Tests: {test_results['total_tests']}")
    logger.info(f"Passed: {test_results['passed']}")
    logger.info(f"Failed: {test_results['failed']}")

    if test_results['failed'] > 0:
        logger.error(f"\nFAILED TESTS ({test_results['failed']}):")
        for error in test_results['errors']:
            logger.error(f"  {error['test']}: {error['error']}")
        return 1
    else:
        logger.info("\n[SUCCESS] ALL TESTS PASSED!")
        return 0

if __name__ == "__main__":
    sys.exit(main())
