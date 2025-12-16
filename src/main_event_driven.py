"""Main Entry Point for Event-Driven Trading Bot"""

import time
import sys
from pathlib import Path
from decimal import Decimal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config_loader import ConfigLoader
from utils.logger import setup_logger
from typing import Optional, Dict
from datetime import datetime
from integrations.bybit import BybitClient
from integrations.bybit_websocket import BybitWebSocketClient
from trading.market_data import MarketData
from trading.market_data_collector import MarketDataCollector
from data.database import Database
from dashboard.bot_state_manager import BotStateManager, BotStatus
from events.fill_event import FillEvent
from events.position_update_event import PositionUpdateEvent
from decimal import Decimal

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
    
    # Initialize Event Queue (before OrderExecutor)
    from events.queue import EventQueue
    event_queue = EventQueue()
    
    # Initialize OrderExecutor (with event queue for FillEvent publishing)
    order_executor = OrderExecutor(trading_state, bybit_client, trading_mode, config, event_queue)
    
    # Initialize PositionMonitor
    position_monitor = PositionMonitor(trading_state, bybit_client, trading_mode, config)
    
    # Initialize Strategies
    strategies = [
        VolatilityExpansionStrategy(config),
        MeanReversionStrategy(config),
        TrendContinuationStrategy(config),
    ]
    
    # Initialize EventLoop (use existing event_queue)
    event_loop = EventLoop(
        trading_state=trading_state,
        risk_engine=risk_engine,
        strategy_allocator=strategy_allocator,
        order_executor=order_executor,
        strategies=strategies,
        config=config,
        trading_mode=trading_mode
    )
    # Share event_queue with order_executor
    order_executor.event_queue = event_loop.event_queue
    
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
    
    # Initialize WebSocket client for LIVE/TESTNET trading
    websocket_client = None
    if trading_mode != "PAPER" and bybit_client and bybit_client.api_key and bybit_client.api_secret:
        try:
            def on_order_update(order_data: Dict) -> None:
                """Handle order update from WebSocket"""
                try:
                    # Map Bybit order data to FillEvent
                    order_status = order_data.get("orderStatus", "")
                    if order_status in ["Filled", "PartiallyFilled"]:
                        fill_event = FillEvent(
                            client_order_id=order_data.get("orderLinkId", ""),
                            exchange_order_id=order_data.get("orderId", ""),
                            symbol=order_data.get("symbol", ""),
                            side=order_data.get("side", ""),
                            filled_quantity=Decimal(str(order_data.get("cumExecQty", 0))),
                            filled_price=Decimal(str(order_data.get("avgPrice", 0))),
                            fill_time=datetime.utcnow(),
                            is_partial=order_status == "PartiallyFilled",
                            remaining_quantity=Decimal(str(order_data.get("leavesQty", 0))),
                            source="BybitWebSocket"
                        )
                        event_loop.publish_event(fill_event)
                        logger.info(f"FillEvent published from WebSocket: {order_data.get('orderLinkId')}")
                except Exception as e:
                    logger.error(f"Error processing order update: {e}", exc_info=True)
            
            def on_position_update(position_data: Dict) -> None:
                """Handle position update from WebSocket"""
                try:
                    # Map Bybit position data to PositionUpdateEvent
                    position_update = PositionUpdateEvent(
                        symbol=position_data.get("symbol", ""),
                        side=position_data.get("side", ""),
                        quantity=Decimal(str(position_data.get("size", 0))),
                        entry_price=Decimal(str(position_data.get("avgPrice", 0))),
                        current_price=Decimal(str(position_data.get("markPrice", 0))),
                        unrealized_pnl=Decimal(str(position_data.get("unrealisedPnl", 0))),
                        realized_pnl=Decimal(str(position_data.get("cumRealisedPnl", 0))) if position_data.get("cumRealisedPnl") else None,
                        position_status="open" if Decimal(str(position_data.get("size", 0))) > 0 else "closed",
                        update_type="modified",
                        source="BybitWebSocket"
                    )
                    event_loop.publish_event(position_update)
                    logger.debug(f"PositionUpdateEvent published from WebSocket: {position_data.get('symbol')}")
                except Exception as e:
                    logger.error(f"Error processing position update: {e}", exc_info=True)
            
            def on_websocket_error(error: Exception) -> None:
                """Handle WebSocket errors"""
                logger.error(f"WebSocket error: {error}", exc_info=True)
            
            websocket_client = BybitWebSocketClient(
                api_key=bybit_client.api_key,
                api_secret=bybit_client.api_secret,
                testnet=(trading_mode == "TESTNET"),
                on_order_update=on_order_update,
                on_position_update=on_position_update,
                on_error=on_websocket_error
            )
            
            # Start WebSocket client
            websocket_client.start()
            logger.info("WebSocket client started for real-time updates")
        
        except Exception as e:
            logger.error(f"Failed to initialize WebSocket client: {e}", exc_info=True)
            logger.warning("Continuing without WebSocket - will rely on reconciliation loop")
    
    # Main loop
    schedule_minutes = config.get("trading", {}).get("schedule_minutes", 1)
    position_check_interval = config.get("trading", {}).get("position_check_interval_seconds", 10)  # Check positions every 10 seconds
    last_reset_date = datetime.utcnow().date()
    last_position_check = datetime.utcnow()
    last_reconcile_time = datetime.utcnow()
    
    # Last heartbeat time for periodic updates
    last_heartbeat_time = datetime.utcnow()

    try:
        while True:
            # Update heartbeat every second (worker is alive)
            current_time = datetime.utcnow()
            if (current_time - last_heartbeat_time).total_seconds() >= 1.0:
                try:
                    db.update_bot_heartbeat()
                    last_heartbeat_time = current_time
                except Exception as e:
                    logger.error(f"Error updating heartbeat: {e}")

            # Read desired state from database (Docker-compatible control)
            try:
                bot_control = db.get_bot_control()
                if not bot_control:
                    logger.warning("bot_control record not found in database")
                    time.sleep(1)
                    continue

                desired_state = bot_control.get('desired_state', 'stopped')

                # Map desired_state to BotStatus for consistency
                if desired_state == 'stopped':
                    current_status = BotStatus.STOPPED
                elif desired_state == 'running':
                    current_status = BotStatus.RUNNING
                elif desired_state == 'paused':
                    current_status = BotStatus.PAUSED
                else:
                    logger.warning(f"Unknown desired_state: {desired_state}")
                    current_status = BotStatus.STOPPED

                # Update actual_state in database
                db.update_bot_actual_state(desired_state)

            except Exception as e:
                logger.error(f"Error reading bot control state from database: {e}", exc_info=True)
                db.update_bot_actual_state('error', str(e))
                time.sleep(1)
                continue

            # If stopped, enter idle loop (do NOT exit)
            if current_status == BotStatus.STOPPED:
                logger.debug("Bot in STOPPED state, idle loop")
                time.sleep(1)
                continue

            if current_status == BotStatus.ERROR:
                logger.error("Bot in error state")
                time.sleep(1)
                continue

            # Check if new day (UTC) - reset daily stats
            current_date = datetime.utcnow().date()
            if current_date != last_reset_date:
                logger.info("New day detected, resetting daily stats")
                trading_state.reset_daily_stats()
                risk_engine._reset_daily_counters_if_needed()
                strategy_allocator._reset_daily_counters_if_needed()
                last_reset_date = current_date

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
            
            # Check risk limits continuously (drawdown, daily loss)
            if current_status == BotStatus.RUNNING:
                try:
                    # Check drawdown limit
                    drawdown_check = risk_engine._check_drawdown_limit()
                    if not drawdown_check["passed"]:
                        logger.critical(f"Drawdown limit breached: {drawdown_check['reason']}")
                        risk_engine._trigger_kill_switch(drawdown_check["reason"])
                        trading_state.disable_trading()
                    
                    # Check max daily loss (using _check_daily_loss_limit which exists)
                    daily_loss_check = risk_engine._check_daily_loss_limit()
                    if not daily_loss_check["passed"]:
                        logger.critical(f"Max daily loss breached: {daily_loss_check['reason']}")
                        risk_engine._trigger_kill_switch(daily_loss_check["reason"])
                        trading_state.disable_trading()
                except Exception as e:
                    logger.error(f"Error checking risk limits: {e}", exc_info=True)
            
            # Reconciliation Loop: Sync orders with exchange state (for LIVE trading)
            if current_status == BotStatus.RUNNING and trading_mode != "PAPER":
                now = datetime.utcnow()
                time_since_last_reconcile = (now - last_reconcile_time).total_seconds()
                
                if time_since_last_reconcile >= 60:  # Reconcile every 60 seconds
                    try:
                        order_executor.reconcile_orders()
                        last_reconcile_time = now
                        logger.debug("Order reconciliation completed")
                    except Exception as e:
                        logger.error(f"Error during reconciliation: {e}", exc_info=True)
            
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
        # Stop WebSocket client
        if websocket_client:
            websocket_client.stop()
        
        event_loop.stop()
        logger.info("Event-driven trading bot stopped")


if __name__ == "__main__":
    main()

