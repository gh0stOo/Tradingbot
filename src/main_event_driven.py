"""Main Entry Point for Event-Driven Trading Bot"""

import time
import sys
from pathlib import Path
from decimal import Decimal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config_loader import ConfigLoader
from utils.logger import setup_logger
from typing import Optional
from integrations.bybit import BybitClient
from trading.market_data import MarketData
from trading.market_data_collector import MarketDataCollector
from data.database import Database
from dashboard.bot_state_manager import BotStateManager, BotStatus

# Event-driven components
from core.trading_state import TradingState
from core.risk_engine import RiskEngine
from core.strategy_allocator import StrategyAllocator
from core.order_executor import OrderExecutor
from core.event_loop import EventLoop
from core.position_monitor import PositionMonitor

# Strategies
from strategies.volatility_expansion import VolatilityExpansionStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.trend_continuation import TrendContinuationStrategy


def get_equity(config: dict, bybit_client: Optional[BybitClient]) -> float:
    """Get account equity"""
    trading_mode = config.get("trading", {}).get("mode", "PAPER")
    
    if trading_mode == "PAPER":
        return config.get("risk", {}).get("paperEquity", 10000)
    else:
        try:
            balance = bybit_client.get_wallet_balance()
            if balance and balance.get("list"):
                account = balance["list"][0]
                equity = float(account.get("totalEquity", account.get("totalWalletBalance", 0)))
                return equity if equity > 0 else config.get("risk", {}).get("paperEquity", 10000)
        except Exception as e:
            print(f"Error getting equity: {e}")
            return config.get("risk", {}).get("paperEquity", 10000)
    
    return config.get("risk", {}).get("paperEquity", 10000)


def main():
    """Main trading bot loop - Event-Driven Architecture"""
    logger = setup_logger()
    logger.info("Starting Event-Driven Trading Bot")
    
    # Load config
    try:
        config_loader = ConfigLoader()
        config = config_loader.config
        logger.info(f"Config loaded. Mode: {config['trading']['mode']}")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return
    
    # Initialize clients
    trading_mode = config["trading"]["mode"]
    bybit_client = None
    
    if trading_mode != "PAPER":
        bybit_config = config.get("bybit", {})
        testnet = bybit_config.get("testnet", False) or (trading_mode == "TESTNET")
        
        if testnet:
            api_key = bybit_config.get("testnetApiKey") or bybit_config.get("api_key")
            api_secret = bybit_config.get("testnetApiSecret") or bybit_config.get("api_secret")
        else:
            api_key = bybit_config.get("apiKey") or bybit_config.get("api_key")
            api_secret = bybit_config.get("apiSecret") or bybit_config.get("api_secret")
        
        if api_key and api_secret:
            bybit_client = BybitClient(api_key, api_secret, testnet)
            logger.info(f"Bybit client initialized: {'TESTNET' if testnet else 'LIVE'}")
        else:
            logger.warning("Bybit credentials not found, using paper mode")
            trading_mode = "PAPER"
    
    # Initialize Bybit client for market data (even in paper mode)
    if not bybit_client:
        testnet = config.get("bybit", {}).get("testnet", False)
        market_data_client = BybitClient("", "", testnet)
    else:
        market_data_client = bybit_client
    
    # Initialize Database
    db_path = config.get("ml", {}).get("database", {}).get("path", "data/trading.db")
    db = Database(db_path)
    logger.info(f"Database initialized at {db_path}")
    
    # Initialize BotStateManager
    bot_state_manager = BotStateManager()
    
    # Initialize TradingState FIRST (before StatePersistence needs it)
    initial_equity = Decimal(str(get_equity(config, bybit_client)))
    trading_state = TradingState(initial_cash=initial_equity)
    
    # Initialize State Persistence (after TradingState is created)
    from core.state_persistence import StatePersistence
    state_persistence = None
    try:
        state_persistence = StatePersistence(db, trading_state)
        # Try to restore latest state
        restored = state_persistence.restore_latest_state()
        if restored:
            logger.info("Trading state restored from database")
        # Register state listener for automatic persistence
        trading_state.register_state_listener(lambda state: state_persistence.save_state())
        logger.info("State persistence initialized")
    except Exception as e:
        logger.warning(f"State persistence initialization failed: {e}")
        state_persistence = None
    
    # Initialize RiskEngine
    risk_engine = RiskEngine(config, trading_state)
    
    # Initialize StrategyAllocator
    strategy_allocator = StrategyAllocator(config, trading_state)
    
    # Initialize OrderExecutor
    order_executor = OrderExecutor(trading_state, bybit_client, trading_mode, config)
    
    # Initialize PositionMonitor
    position_monitor = PositionMonitor(trading_state, bybit_client, trading_mode, config)
    
    # Initialize Strategies
    strategies = [
        VolatilityExpansionStrategy(config),
        MeanReversionStrategy(config),
        TrendContinuationStrategy(config),
    ]
    
    # Initialize EventLoop
    event_loop = EventLoop(
        trading_state=trading_state,
        risk_engine=risk_engine,
        strategy_allocator=strategy_allocator,
        order_executor=order_executor,
        strategies=strategies,
        config=config,
        trading_mode=trading_mode
    )
    
    # Initialize MarketData
    market_data = MarketData(market_data_client)
    market_data_collector = MarketDataCollector(
        market_data=market_data,
        event_publisher=event_loop.publish_event
    )
    
    # Start event loop
    event_loop.start()
    
    # Get symbols to trade
    top_n = config.get("universe", {}).get("topN", 50)
    min_volume = config.get("universe", {}).get("minVolume24h", 5000000)
    
    logger.info("Event-driven trading bot initialized. Starting main loop...")
    
    # Main loop
    schedule_minutes = config.get("trading", {}).get("schedule_minutes", 1)
    last_reset_date = datetime.utcnow().date()
    
    try:
        while True:
            # Check if new day (UTC) - reset daily stats
            current_date = datetime.utcnow().date()
            if current_date != last_reset_date:
                logger.info("New day detected, resetting daily stats")
                trading_state.reset_daily_stats()
                risk_engine._reset_daily_counters_if_needed()
                strategy_allocator._reset_daily_counters_if_needed()
                last_reset_date = current_date
            
            # Check bot state
            current_status = bot_state_manager.get_status()
            
            if current_status == BotStatus.STOPPED:
                logger.info("Bot stopped via BotStateManager")
                time.sleep(5)
                continue
            
            if current_status == BotStatus.ERROR:
                logger.error("Bot in error state")
                time.sleep(5)
                continue
            
            # Enable/disable trading based on state
            if current_status == BotStatus.RUNNING:
                if not trading_state.trading_enabled:
                    trading_state.enable_trading()
                    logger.info("Trading enabled")
            else:
                if trading_state.trading_enabled:
                    trading_state.disable_trading()
                    logger.info("Trading disabled")
            
            # Collect market data and publish events
            if current_status == BotStatus.RUNNING:
                try:
                    top_coins = market_data.get_top_coins(top_n=top_n, min_volume=min_volume)
                    symbols = [coin["symbol"] for coin in top_coins]
                    
                    if symbols:
                        logger.info(f"Collecting market data for {len(symbols)} symbols")
                        market_data_collector.collect_and_publish(symbols)
                    
                except Exception as e:
                    logger.error(f"Error collecting market data: {e}", exc_info=True)
            
            # Monitor positions more frequently (every position_check_interval seconds)
            # IMPORTANT: Only monitor positions for PAPER trading
            # For LIVE trading, exchange handles stop-loss/take-profit orders
            if current_status == BotStatus.RUNNING and trading_mode == "PAPER":
                now = datetime.utcnow()
                time_since_last_check = (now - last_position_check).total_seconds()
                
                if time_since_last_check >= position_check_interval:
                    try:
                        # Get current prices for ALL open positions (not just top coins)
                        open_positions = trading_state.get_open_positions()
                        if open_positions:
                            # Get top coins for fast price lookup
                            try:
                                top_coins = market_data.get_top_coins(top_n=top_n, min_volume=min_volume)
                            except:
                                top_coins = []
                            
                            current_prices = {}
                            
                            for symbol, _ in open_positions.items():
                                # First try to find in top_coins (fastest)
                                coin_data = next((c for c in top_coins if c["symbol"] == symbol), None)
                                if coin_data:
                                    price = coin_data.get("lastPrice")
                                    if price and price > 0:
                                        current_prices[symbol] = Decimal(str(price))
                                        continue
                                
                                # If not in top coins, fetch individually
                                try:
                                    tickers = market_data_client.get_tickers()
                                    for ticker in tickers:
                                        if ticker.get("symbol") == symbol:
                                            price = ticker.get("lastPrice", 0)
                                            if price and float(price) > 0:
                                                current_prices[symbol] = Decimal(str(price))
                                            break
                                    else:
                                        # Symbol not found in tickers - log warning
                                        logger.warning(f"Symbol {symbol} not found in tickers, cannot check position")
                                except Exception as e:
                                    logger.warning(f"Could not fetch price for {symbol}: {e}")
                            
                            if current_prices:
                                exits = position_monitor.check_positions(current_prices)
                                if exits:
                                    logger.info(f"Closed {len(exits)} positions: {[e['exit_reason'] for e in exits]}")
                            
                            last_position_check = now
                    except Exception as e:
                        logger.error(f"Error monitoring positions: {e}", exc_info=True)
            
            # Sleep with shorter interval to allow more frequent position checks
            # But don't sleep too short to avoid excessive CPU usage
            sleep_seconds = min(schedule_minutes * 60, position_check_interval)
            time.sleep(sleep_seconds)
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}", exc_info=True)
    finally:
        event_loop.stop()
        logger.info("Event-driven trading bot stopped")


if __name__ == "__main__":
    main()

