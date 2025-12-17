"""
Quick Test für Refactored Bot Architecture

Testet die neue Architektur mit minimalem Setup:
- State Machine
- Strategy Orchestrator
- Eine einzelne Strategie (emaTrend)
- Echte Marktdaten von Bybit

Zeigt deutlich:
- State Transitions
- Strategy Evaluation
- Signal Generation
- Deterministische Ausführung
"""

import sys
from pathlib import Path
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.config_loader import ConfigLoader
from utils.logger import setup_logger
from integrations.bybit import BybitClient
from trading.market_data import MarketData
from trading.order_manager import OrderManager
from trading.bot_refactored import TradingBotRefactored
from data.database import Database
from data.data_collector import DataCollector
from data.position_tracker import PositionTracker


def main():
    """Quick test der neuen Architektur"""

    # Setup logging
    logger = setup_logger()
    logger.info("=" * 70)
    logger.info("QUICK TEST: Refactored Bot Architecture")
    logger.info("=" * 70)

    # Load config
    try:
        config = ConfigLoader().config
        logger.info("[OK] Config loaded")
    except Exception as e:
        logger.error(f"[ERROR] Failed to load config: {e}")
        return

    # Initialize Bybit client (public API)
    bybit = BybitClient("", "", testnet=False)
    market_data = MarketData(bybit)
    logger.info("[OK] Market data client initialized")

    # Initialize database
    db_path = config.get("ml", {}).get("database", {}).get("path", "data/trading.db")
    db = Database(db_path)
    data_collector = DataCollector(db)
    position_tracker = PositionTracker(db)
    logger.info(f"[OK] Database initialized: {db_path}")

    # Initialize order manager (paper mode)
    order_manager = OrderManager(None, "PAPER", position_tracker, data_collector)
    logger.info("[OK] Order manager initialized (PAPER mode)")

    # Initialize REFACTORED bot
    logger.info("\n" + "=" * 70)
    logger.info("Initializing REFACTORED Bot...")
    logger.info("=" * 70)

    bot = TradingBotRefactored(
        config=config,
        market_data=market_data,
        order_manager=order_manager,
        data_collector=data_collector,
        position_tracker=position_tracker
    )

    logger.info("[OK] Refactored Bot initialized")

    # Get bot status
    status = bot.get_status()
    logger.info("\n" + "-" * 70)
    logger.info("BOT STATUS:")
    logger.info(f"  State Machine: {status['stateMachine']['state']}")
    logger.info(f"  Can Evaluate: {status['stateMachine']['canEvaluate']}")
    logger.info(f"  Open Positions: {status['positions']}")
    logger.info(f"  ML Enabled: {status['mlEnabled']}")

    logger.info("\n  Orchestrator:")
    logger.info(f"    Total Evaluations: {status['orchestrator']['total_evaluations']}")
    logger.info(f"    Signals Generated: {status['orchestrator']['signals_generated']}")
    logger.info(f"    Registered Strategies: {list(status['orchestrator']['strategies'].keys())}")
    logger.info("-" * 70)

    # Get market data
    logger.info("\n" + "=" * 70)
    logger.info("Fetching Market Data...")
    logger.info("=" * 70)

    try:
        # Get BTCUSDT specifically
        symbol = "BTCUSDT"
        logger.info(f"Testing with {symbol}...")

        # Get symbol info from top coins
        top_coins = market_data.get_top_coins(top_n=100, min_volume=1000000)
        symbol_info = None
        for coin in top_coins:
            if coin["symbol"] == symbol:
                symbol_info = coin
                break

        if not symbol_info:
            # Fallback: create minimal symbol_info
            logger.warning(f"[WARN] {symbol} not in top coins, using minimal info")
            symbol_info = {
                "symbol": symbol,
                "tickSize": "0.01",
                "qtyStep": "0.001",
                "minOrderQty": "0.001",
                "volume24h": 0
            }

        logger.info(f"[OK] Symbol info retrieved: {symbol}")

        # Get BTC price
        btc_price = market_data.get_btc_price()
        logger.info(f"[OK] BTC Price: ${btc_price:,.2f}")

        # Get equity
        equity = config.get("risk", {}).get("paperEquity", 10000)
        logger.info(f"[OK] Paper Equity: ${equity:,.2f}")

    except Exception as e:
        logger.error(f"[ERROR] Error fetching market data: {e}")
        import traceback
        traceback.print_exc()
        return

    # Process symbol (this tests the ENTIRE new architecture)
    logger.info("\n" + "=" * 70)
    logger.info(f"Processing {symbol} with NEW Architecture...")
    logger.info("=" * 70)

    try:
        result = bot.process_symbol(
            symbol=symbol,
            symbol_info=symbol_info,
            btc_price=btc_price,
            equity=equity
        )

        if result:
            logger.info("\n" + "-" * 70)
            logger.info("RESULT:")

            # Signal info
            if result.get("signal"):
                signal = result["signal"]
                logger.info(f"  Signal: {signal.get('side', 'N/A')}")
                logger.info(f"  Strategy: {signal.get('strategy', 'N/A')}")
                logger.info(f"  Confidence: {signal.get('confidence', 0):.2%}")
                logger.info(f"  Regime Weight: {signal.get('regimeWeight', 0):.2f}")
                logger.info(f"  Base Confidence: {signal.get('baseConfidence', 0):.2%}")
            else:
                logger.info("  Signal: None")

            # Execution info
            if result.get("execution"):
                execution = result["execution"]
                logger.info(f"  Execution Success: {execution.get('success', False)}")
                if execution.get("success"):
                    logger.info(f"  Entry Price: ${execution.get('price', 0):,.2f}")
                    logger.info(f"  Quantity: {execution.get('qty', 0):.4f}")
                    logger.info(f"  Stop Loss: ${execution.get('stopLoss', 0):,.2f}")
                    logger.info(f"  Take Profit: ${execution.get('takeProfit', 0):,.2f}")

            # State Machine info
            if result.get("stateMachine"):
                sm = result["stateMachine"]
                logger.info(f"  State After: {sm.get('state', 'N/A')}")
                logger.info(f"  Can Evaluate: {sm.get('canEvaluate', False)}")

            # Regime info
            if result.get("regime"):
                regime = result["regime"]
                logger.info(f"  Market Regime: {regime.get('type', 'N/A')}")
                logger.info(f"  Is Bullish: {regime.get('isBullish', False)}")
                logger.info(f"  Is Trending: {regime.get('isTrending', False)}")

            logger.info("-" * 70)

        else:
            logger.info("[INFO] No result returned (no valid signal)")

    except Exception as e:
        logger.error(f"[ERROR] Error processing symbol: {e}")
        import traceback
        traceback.print_exc()
        return

    # Get updated status
    logger.info("\n" + "=" * 70)
    logger.info("FINAL BOT STATUS:")
    logger.info("=" * 70)

    status = bot.get_status()
    logger.info(f"  State Machine: {status['stateMachine']['state']}")
    logger.info(f"  Open Positions: {status['positions']}")
    logger.info(f"  Total Evaluations: {status['orchestrator']['total_evaluations']}")
    logger.info(f"  Signals Generated: {status['orchestrator']['signals_generated']}")
    logger.info(f"  Signal Rate: {status['orchestrator']['signal_rate']:.2%}")

    logger.info("\n  Strategy Statistics:")
    for strategy_name, stats in status['orchestrator']['strategies'].items():
        logger.info(f"    {strategy_name}:")
        logger.info(f"      Evaluated: {stats['evaluated']}")
        logger.info(f"      Signals: {stats['signals']}")
        logger.info(f"      Executed: {stats['executed']}")

    logger.info("\n" + "=" * 70)
    logger.info("TEST COMPLETE")
    logger.info("=" * 70)

    # Cleanup
    db.close()
    logger.info("\n[OK] Database closed")


if __name__ == "__main__":
    main()
