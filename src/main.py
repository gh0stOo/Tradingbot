"""Main Entry Point for Trading Bot"""

import time
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config_loader import ConfigLoader
from utils.logger import setup_logger
from integrations.bybit import BybitClient
from integrations.notion import NotionIntegration
from trading.market_data import MarketData
from trading.order_manager import OrderManager
from trading.bot import TradingBot
from api.bot_integration import BotAPIClient
from data.database import Database
from data.data_collector import DataCollector
from data.position_tracker import PositionTracker
from trading.position_manager import PositionManager
from monitoring.health_check import HealthChecker
from monitoring.alerting import AlertManager, AlertLevel
from dashboard.bot_state_manager import BotStateManager, BotStatus

# FIX #6: Global state manager to ensure same instance in shutdown handler
# This prevents creating a new instance in the exception handler
global_state_manager = None

def get_equity(config: dict, bybit_client: BybitClient) -> float:
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
            # Import logger locally since this function is called before main logger setup
            from utils.logger import setup_logger
            logger = setup_logger()
            logger.error(f"Error getting equity: {e}")
            return config.get("risk", {}).get("paperEquity", 10000)
    
    return config.get("risk", {}).get("paperEquity", 10000)

def main():
    """Main trading bot loop - SQLite-based control"""
    global global_state_manager
    
    logger = setup_logger()
    logger.info("Starting Trading Bot (SQLite-based control)")
    
    # Initialize BotControlDB FIRST (before anything else)
    from dashboard.bot_control_db import BotControlDB
    import os
    db_path = os.getenv("TRADING_DB_PATH", "data/trading.db")
    bot_control_db = BotControlDB(db_path)
    
    # Initial heartbeat and state
    bot_control_db.update_actual_state("stopped")
    bot_control_db.update_heartbeat()
    logger.info("BotControlDB initialized - Worker will monitor desired_state from SQLite")
    
    # Load config
    try:
        config_loader = ConfigLoader()
        config = config_loader.config
        logger.info(f"Config loaded. Mode: {config['trading']['mode']}")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        bot_control_db.update_actual_state("error", f"Config load failed: {str(e)}")
        return
    
    # Initialize clients
    trading_mode = config["trading"]["mode"]
    bybit_client = None
    
    if trading_mode != "PAPER":
        bybit_config = config.get("bybit", {})
        testnet = bybit_config.get("testnet", False) or (trading_mode == "TESTNET")
        
        # Use testnet keys if testnet, otherwise use live keys
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
    
    # Initialize Notion
    notion_client = None
    try:
        notion_config = config.get("notion", {})
        if notion_config.get("enabled", False):
            api_key = notion_config.get("apiKey") or notion_config.get("api_key") or config_loader.get("notion.api_key")
            databases = notion_config.get("databases", {})
            
            if api_key and databases:
                notion_client = NotionIntegration(api_key, databases)
                logger.info("Notion client initialized")
            else:
                logger.warning("Notion enabled but API key or databases not found")
        else:
            logger.info("Notion integration disabled in config")
    except Exception as e:
        logger.warning(f"Notion initialization failed: {e}")
    
    # Initialize Bybit client for market data
    # Even in paper mode, we need public API access for market data
    if not bybit_client:
        # Use testnet URL if configured, otherwise mainnet
        testnet = config.get("bybit", {}).get("testnet", False)
        market_data_client = BybitClient("", "", testnet)
    else:
        market_data_client = bybit_client
    
    # Initialize Database and Data Collection
    db_path = config.get("ml", {}).get("database", {}).get("path", "data/trading.db")
    db = Database(db_path)
    data_collector = DataCollector(db)
    position_tracker = PositionTracker(db)
    logger.info(f"Database initialized at {db_path}")
    
    # Initialize Position Manager (for exit monitoring)
    position_manager = PositionManager(
        position_tracker=position_tracker,
        bybit_client=bybit_client if bybit_client else market_data_client,
        check_interval=5.0,  # Check every 5 seconds
        auto_close_enabled=config.get("positionManagement", {}).get("autoClose", True),
        db=db
    )
    logger.info("Position Manager initialized")
    
    # Initialize Monitoring Systems
    health_checker = HealthChecker()
    alert_manager = AlertManager()
    
    # Register Discord alert handler if configured
    # NOTE: Discord alerting temporarily disabled due to module issues
    alerts_config = config.get("alerts", {})
    discord_webhook = None
    if False:  # Disabled for now
        discord_webhook = alerts_config.get("discordWebhook")
        if discord_webhook:
            try:
                from monitoring.alerting import discord_alert_handler
                alert_manager.register_handler(discord_alert_handler(discord_webhook))
                logger.info("Discord alert handler registered")
            except Exception as e:
                logger.warning(f"Failed to register Discord alert handler: {e}")
        else:
            logger.warning("Alerts enabled but Discord webhook not configured")
    else:
        logger.info("Discord alerts disabled (module not available)")
    
    logger.info("Monitoring systems initialized")

    market_data = MarketData(market_data_client)
    order_manager = OrderManager(bybit_client, trading_mode, position_tracker, data_collector)
    bot = TradingBot(config, market_data, order_manager, data_collector, position_tracker, position_manager=position_manager)

    # FIX #6: Initialize State Manager for Bot Control (as global)
    if not global_state_manager:
        global_state_manager = BotStateManager()
    logger.info("Bot State Manager initialized")

    # Initialize Genetic Algorithm Optimization (Phase 2.5)
    ga_scheduler = None
    if config.get("ml", {}).get("geneticAlgorithm", {}).get("enabled", False):
        try:
            from ml.genetic_optimizer import GeneticAlgorithmOptimizer
            from ml.backtest_runner import BacktestRunner
            from ml.parameter_scheduler import ParameterScheduler
            
            # Define parameter bounds (can be customized)
            parameter_bounds = {}
            if "strategies" in config:
                for strategy_name in config["strategies"].keys():
                    parameter_bounds[f"strategy_weight_{strategy_name}"] = (0.0, 2.0)
            if "risk" in config:
                parameter_bounds["risk_riskPct"] = (0.01, 0.05)
                parameter_bounds["risk_minRR"] = (1.0, 3.0)
            if "ensemble" in config:
                parameter_bounds["minConfidence"] = (0.4, 0.8)
                parameter_bounds["minQualityScore"] = (0.3, 0.7)
            
            if parameter_bounds:
                ga_config = config["ml"]["geneticAlgorithm"]
                optimizer = GeneticAlgorithmOptimizer(
                    parameter_bounds=parameter_bounds,
                    population_size=ga_config.get("populationSize", 50),
                    mutation_rate=ga_config.get("mutationRate", 0.1),
                    crossover_rate=ga_config.get("crossoverRate", 0.7),
                    elite_size=ga_config.get("eliteSize", 5)
                )
                
                backtest_runner = BacktestRunner(
                    database_path=config.get("ml", {}).get("database", {}).get("path", "data/trading.db"),
                    rolling_window_trades=ga_config.get("rollingWindowTrades", 500),
                    initial_equity=config.get("risk", {}).get("paperEquity", 10000.0)
                )
                
                ga_scheduler = ParameterScheduler(
                    optimizer=optimizer,
                    backtest_runner=backtest_runner,
                    base_config=config,
                    schedule_type=ga_config.get("scheduleType", "daily"),
                    optimization_hour=ga_config.get("optimizationHour", 2),
                    optimization_day=ga_config.get("optimizationDay", 0),
                    enabled=ga_config.get("enabled", False)
                )
                
                # Set callback to update bot config with optimized parameters
                def update_config_with_params(optimized_params):
                    logger.info("Updating bot configuration with optimized parameters...")
                    # Update strategy weights
                    for key, value in optimized_params.items():
                        if key.startswith("strategy_weight_"):
                            strategy_name = key.replace("strategy_weight_", "")
                            if "strategies" in config and strategy_name in config["strategies"]:
                                config["strategies"][strategy_name]["weight"] = value
                                bot.strategies.config["strategies"][strategy_name]["weight"] = value
                    logger.info("Bot configuration updated with optimized parameters")
                
                ga_scheduler.set_optimization_callback(update_config_with_params)
                ga_scheduler.start()
                logger.info("Genetic Algorithm Parameter Scheduler started")
        except ImportError as e:
            logger.warning(f"Genetic Algorithm modules not available: {e}")
        except Exception as e:
            logger.error(f"Error initializing Genetic Algorithm: {e}", exc_info=True)
    
    # Initialize Online Learning Manager (Phase 3)
    if hasattr(bot, 'online_learning_manager') and bot.online_learning_manager and hasattr(bot.online_learning_manager, 'enabled') and bot.online_learning_manager.enabled:
        logger.info("Online Learning Manager is enabled and ready")
    
    # Initialize Training Scheduler (Phase 3)
    # NOTE: Training Scheduler modules not yet available - disabled for now
    training_scheduler = None
    # try:
    #     from ml.training_scheduler import TrainingScheduler, create_training_function
    #
    #     training_function = create_training_function(config)
    #     training_scheduler = TrainingScheduler(
    #         data_collector=data_collector,
    #         training_function=training_function,
    #         config=config,
    #         enabled=config.get("ml", {}).get("trainingScheduler", {}).get("enabled", False)
    #     )
    #     training_scheduler.start()
    #     logger.info("Training Scheduler started")
    # except ImportError as e:
    #     logger.warning(f"Training Scheduler modules not available: {e}")
    # except Exception as e:
    #     logger.error(f"Error initializing Training Scheduler: {e}", exc_info=True)
    
    # Initialize API client for n8n integration (optional)
    api_client = None
    try:
        # Check if API server should be used
        use_api = config.get("api", {}).get("enabled", True)
        if use_api:
            # In Docker, use service name instead of localhost
            import os
            # Check if we're running in Docker
            is_docker = os.path.exists("/.dockerenv")
            
            # In Docker, always use service name (ignore config URL that might use localhost)
            if is_docker:
                api_base_url = "http://trading-bot-api:8000"  # Docker service name + internal port
                logger.info(f"Using Docker service URL (overriding config): {api_base_url}")
            else:
                # Local development - use config URL or default to external port
                config_url = config.get("api", {}).get("baseUrl")
                api_base_url = config_url if config_url else "http://localhost:1337"
                logger.info(f"Using API URL: {api_base_url}")
            
            api_client = BotAPIClient(api_base_url)
            logger.info(f"API client initialized: {api_base_url}")
    except Exception as e:
        logger.warning(f"API client not initialized: {e}")
    
    # Update state tracking before circuit breaker check
    bot.update_state_tracking()
    
    # Check circuit breaker
    circuit_breaker = bot.risk_manager.check_circuit_breaker(
        current_positions=bot.current_positions,
        daily_pnl=bot.daily_pnl,
        equity=get_equity(config, bybit_client) if bybit_client else config["risk"]["paperEquity"],
        loss_streak=bot.loss_streak
    )
    
    if circuit_breaker.get("tripped"):
        reason = circuit_breaker['reason']
        logger.warning(f"Circuit breaker tripped: {reason}")
        
        # Send alert
        alert_manager.send_alert(
            level=AlertLevel.CRITICAL,
            title="Circuit Breaker Tripped",
            message=f"Trading halted: {reason}",
            source="risk_manager",
            metadata=circuit_breaker
        )
        return
    
    # Get equity
    equity = get_equity(config, bybit_client) if bybit_client else config["risk"]["paperEquity"]
    logger.info(f"Account equity: {equity} USDT")
    
    # Get market data
    try:
        logger.info("Fetching market data...")
        top_coins = market_data.get_top_coins(
            top_n=config["universe"]["topN"],
            min_volume=config["universe"]["minVolume24h"]
        )
        btc_price = market_data.get_btc_price()
        logger.info(f"Found {len(top_coins)} coins. BTC Price: {btc_price}")
        
        # Update BTC tracker with initial price
        bot.btc_tracker.update_price(btc_price)
    except Exception as e:
        logger.error(f"Failed to fetch market data: {e}")
        return
    
    # Process each symbol (with optional parallel processing)
    parallel_config = config.get("processing", {})
    use_parallel = parallel_config.get("enabled", True)
    max_workers = parallel_config.get("maxWorkers", 5)
    batch_size = parallel_config.get("batchSize", 10)
    rate_limit = parallel_config.get("rateLimit", 10)  # Max concurrent API calls
    
    if use_parallel and len(top_coins) > 1:
        logger.info(f"Processing {len(top_coins)} coins in parallel (max_workers={max_workers})")
        from utils.parallel_processor import process_coins_parallel
        
        def process_coin(coin_data):
            symbol = coin_data["symbol"]
            try:
                result = bot.process_symbol(symbol, coin_data, btc_price, equity)
                if result:
                    # Add trading mode to result for Discord
                    result["mode"] = trading_mode
                    
                    # Send Discord notification for signal (always)
                    if discord_webhook and result.get("signal", {}).get("side") != "Hold":
                        from monitoring.alerting import send_discord_trade_signal
                        send_discord_trade_signal(discord_webhook, result, signal_type="signal")
                    
                    # Log to Notion if available
                    if notion_client and result.get("execution", {}).get("success"):
                        notion_client.log_signal(result)
                        notion_client.log_execution(result)
                    
                    # Send Discord notification for execution (if executed)
                    if discord_webhook and result.get("execution", {}).get("success"):
                        from monitoring.alerting import send_discord_trade_signal
                        send_discord_trade_signal(discord_webhook, result, signal_type="execution")
                    
                    # Send signal to API endpoint for n8n integration
                    if api_client and result.get("execution", {}).get("success"):
                        api_client.send_signal(result)
                    
                    logger.info(f"Trade signal for {symbol}: {result.get('signal', {}).get('side')} "
                              f"(Confidence: {result.get('signal', {}).get('confidence', 0):.2f})")
                return result
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                return None
        
        results = process_coins_parallel(
            coins=top_coins,
            process_func=process_coin,
            max_workers=max_workers,
            batch_size=batch_size,
            rate_limit=rate_limit
        )
        results = [r for r in results if r]  # Filter None results
    else:
        # Sequential processing
        results = []
        for coin in top_coins:
            symbol = coin["symbol"]
            logger.info(f"Processing {symbol}...")
            
            try:
                result = bot.process_symbol(symbol, coin, btc_price, equity)
                if result:
                    results.append(result)
                    
                    # Add trading mode to result for Discord
                    result["mode"] = trading_mode
                    
                    # Send Discord notification for signal (always)
                    if discord_webhook and result.get("signal", {}).get("side") != "Hold":
                        from monitoring.alerting import send_discord_trade_signal
                        send_discord_trade_signal(discord_webhook, result, signal_type="signal")
                    
                    # Log to Notion if available
                    if notion_client and result.get("execution", {}).get("success"):
                        notion_client.log_signal(result)
                        notion_client.log_execution(result)
                        logger.info(f"Logged {symbol} to Notion")
                    
                    # Send Discord notification for execution (if executed)
                    if discord_webhook and result.get("execution", {}).get("success"):
                        from monitoring.alerting import send_discord_trade_signal
                        send_discord_trade_signal(discord_webhook, result, signal_type="execution")
                    
                    logger.info(f"Trade signal for {symbol}: {result.get('signal', {}).get('side')} "
                              f"(Confidence: {result.get('signal', {}).get('confidence', 0):.2f})")
                    
                    # Send signal to API endpoint for n8n integration
                    if api_client and result.get("execution", {}).get("success"):
                        api_client.send_signal(result)
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                continue
    
    logger.info(f"Processing complete. {len(results)} signals generated.")
    
    # Set bot reference in state manager
    if global_state_manager:
        global_state_manager.set_bot_reference(bot)
    
    # Start position monitoring if enabled
    if config.get("positionManagement", {}).get("monitoringEnabled", True):
        try:
            position_manager.start_monitoring()
            logger.info("Position monitoring started")
        except Exception as e:
            logger.warning(f"Failed to start position monitoring: {e}")
    
    # Register callback for emergency stop
    def on_emergency_stop(status: BotStatus):
        """Handle emergency stop callback"""
        if status == BotStatus.STOPPED:
            logger.warning("Emergency stop triggered - closing all positions")
            # Close all open positions
            if position_manager:
                open_positions = position_tracker.get_open_positions()
                for trade_id, position in open_positions.items():
                    try:
                        # Get current price and close position
                        current_price = position_manager.get_current_price(position["symbol"])
                        if current_price:
                            position_manager.close_position_auto(trade_id, current_price, "Emergency Stop")
                    except Exception as e:
                        logger.error(f"Error closing position {trade_id} during emergency stop: {e}")
    
    if global_state_manager:
        global_state_manager.register_callback(on_emergency_stop)
    
    # Main bot loop - runs continuously
    loop_interval = config.get("trading", {}).get("loopInterval", 5)  # Default 5 seconds (CRITICAL FIX: was 300)
    logger.info(f"Starting main loop with interval: {loop_interval} seconds")
    logger.info("Bot is now running. Use Dashboard API to control: /api/bot/start, /api/bot/pause, /api/bot/stop")
    logger.info("Worker reads desired_state from SQLite and writes actual_state + heartbeat")
    try:
        startup_state = global_state_manager.status.value if global_state_manager else "stopped"
        bot_control_db.update_actual_state(startup_state)
        bot_control_db.update_heartbeat()
    except Exception as e:
        logger.warning(f"Failed to persist startup state to DB: {e}")
    
    while True:
        # Check desired_state from SQLite (worker pattern)
        desired_state = bot_control_db.get_desired_state()
        
        if desired_state is None:
            logger.error("Error reading desired_state from SQLite")
            bot_control_db.update_actual_state("error", "Error reading desired_state")
            time.sleep(5)
            continue
        
        # Map desired_state to BotStatus
        if desired_state == "running":
            target_status = BotStatus.RUNNING
        elif desired_state == "paused":
            target_status = BotStatus.PAUSED
        else:  # stopped
            target_status = BotStatus.STOPPED
        
        # Check current status from state manager
        current_status = global_state_manager.status if global_state_manager else BotStatus.STOPPED
        
        # Track if a state transition occurred (to avoid overwriting actual_state)
        state_transition_occurred = False
        
        # Handle state transitions based on desired_state
        if desired_state == "stopped" and current_status != BotStatus.STOPPED:
            logger.info("Desired state is 'stopped' - stopping bot")
            if global_state_manager:
                global_state_manager.set_status(BotStatus.STOPPED)
            bot_control_db.update_actual_state("stopped")
            state_transition_occurred = True
            # Continue in idle loop (don't exit!)
            time.sleep(1)
            continue
        
        if desired_state == "paused" and current_status == BotStatus.RUNNING:
            logger.info("Desired state is 'paused' - pausing bot")
            if global_state_manager:
                global_state_manager.set_status(BotStatus.PAUSED)
            bot_control_db.update_actual_state("paused")
            state_transition_occurred = True
            # Re-read current_status after state change
            current_status = global_state_manager.status if global_state_manager else BotStatus.STOPPED
        
        if desired_state == "running" and current_status == BotStatus.STOPPED:
            logger.info("Desired state is 'running' - starting bot")
            # Note: Bot components already initialized at module level
            # This just sets the status to RUNNING
            if global_state_manager:
                global_state_manager.set_status(BotStatus.RUNNING)
            # CRITICAL: Update actual_state immediately in SQLite
            bot_control_db.update_actual_state("running")
            state_transition_occurred = True
            # Re-read current_status after state change to ensure it's RUNNING
            current_status = global_state_manager.status if global_state_manager else BotStatus.RUNNING
            # CRITICAL: Skip stopped/paused handlers and go directly to trading loop
            # Don't continue here - let the code fall through to trading execution
        
        if desired_state == "running" and current_status == BotStatus.PAUSED:
            logger.info("Desired state is 'running' - resuming bot")
            if global_state_manager:
                global_state_manager.set_status(BotStatus.RUNNING)
            bot_control_db.update_actual_state("running")
            state_transition_occurred = True
            # Re-read current_status after state change
            current_status = global_state_manager.status if global_state_manager else BotStatus.RUNNING
            # Continue to trading loop (don't go to stopped/paused handlers)
        
        # Update actual_state in SQLite based on current_status
        # BUT ONLY if no state transition occurred (to avoid overwriting the transition)
        if not state_transition_occurred:
            if current_status == BotStatus.RUNNING:
                bot_control_db.update_actual_state("running")
            elif current_status == BotStatus.PAUSED:
                bot_control_db.update_actual_state("paused")
            elif current_status == BotStatus.ERROR:
                error_msg = global_state_manager.error_message if global_state_manager else "Unknown error"
                bot_control_db.update_actual_state("error", error_msg)
            else:  # STOPPED
                bot_control_db.update_actual_state("stopped")

        # Persist a heartbeat + actual state every loop iteration so the web panel stays in sync
        logger.info(f"Syncing bot state: desired={desired_state}, current={current_status.value}")
        try:
            current_state_value = global_state_manager.status.value if global_state_manager else target_status.value
            bot_control_db.update_actual_state(current_state_value)
            bot_control_db.update_heartbeat()
        except Exception as e:
            logger.warning(f"Failed to persist bot heartbeat/state: {e}")
        
        # Handle paused state
        if current_status == BotStatus.PAUSED:
            logger.debug("Bot is paused, waiting...")
            time.sleep(1)
            continue
        
        # Handle stopped state (idle loop - don't exit!)
        if current_status == BotStatus.STOPPED:
            logger.debug("Bot is stopped, waiting in idle loop...")
            time.sleep(1)
            continue
        
        # Handle error state
        if current_status == BotStatus.ERROR:
            error_msg = global_state_manager.error_message if global_state_manager else "Unknown error"
            logger.error(f"Bot in error state: {error_msg}")
            # Wait and check again
            time.sleep(5)
            continue
        
        # Bot is RUNNING - execute trading cycle
        try:
            # Update state tracking
            bot.update_state_tracking()
            
            # Check circuit breaker
            circuit_breaker = bot.risk_manager.check_circuit_breaker(
                current_positions=bot.current_positions,
                daily_pnl=bot.daily_pnl,
                equity=get_equity(config, bybit_client) if bybit_client else config["risk"]["paperEquity"],
                loss_streak=bot.loss_streak
            )
            
            if circuit_breaker.get("tripped"):
                reason = circuit_breaker['reason']
                logger.warning(f"Circuit breaker tripped: {reason}")
                if global_state_manager:
                    global_state_manager.set_status(BotStatus.ERROR, f"Circuit breaker: {reason}")
                
                # Send alert
                alert_manager.send_alert(
                    level=AlertLevel.CRITICAL,
                    title="Circuit Breaker Tripped",
                    message=f"Trading halted: {reason}",
                    source="risk_manager",
                    metadata=circuit_breaker
                )
                time.sleep(60)  # Wait before retrying
                continue
            
            # Get equity
            equity = get_equity(config, bybit_client) if bybit_client else config["risk"]["paperEquity"]
            
            # Get market data
            try:
                logger.info("Fetching market data...")
                top_coins = market_data.get_top_coins(
                    top_n=config["universe"]["topN"],
                    min_volume=config["universe"]["minVolume24h"]
                )
                btc_price = market_data.get_btc_price()
                logger.info(f"Found {len(top_coins)} coins. BTC Price: {btc_price}")
                
                # Update BTC tracker with current price
                bot.btc_tracker.update_price(btc_price)
            except Exception as e:
                logger.error(f"Failed to fetch market data: {e}")
                if global_state_manager:
                    global_state_manager.set_status(BotStatus.ERROR, f"Market data fetch failed: {e}")
                time.sleep(60)
                continue
            
            # Process each symbol (with optional parallel processing)
            parallel_config = config.get("processing", {})
            use_parallel = parallel_config.get("enabled", True)
            max_workers = parallel_config.get("maxWorkers", 5)
            batch_size = parallel_config.get("batchSize", 10)
            rate_limit = parallel_config.get("rateLimit", 10)
            
            if use_parallel and len(top_coins) > 1:
                logger.info(f"Processing {len(top_coins)} coins in parallel (max_workers={max_workers})")
                from utils.parallel_processor import process_coins_parallel
                
                def process_coin(coin_data):
                    symbol = coin_data["symbol"]
                    try:
                        result = bot.process_symbol(symbol, coin_data, btc_price, equity)
                        if result:
                            result["mode"] = trading_mode
                            
                            if discord_webhook and result.get("signal", {}).get("side") != "Hold":
                                from monitoring.alerting import send_discord_trade_signal
                                send_discord_trade_signal(discord_webhook, result, signal_type="signal")
                            
                            if notion_client and result.get("execution", {}).get("success"):
                                notion_client.log_signal(result)
                                notion_client.log_execution(result)
                            
                            if discord_webhook and result.get("execution", {}).get("success"):
                                from monitoring.alerting import send_discord_trade_signal
                                send_discord_trade_signal(discord_webhook, result, signal_type="execution")
                            
                            if api_client and result.get("execution", {}).get("success"):
                                api_client.send_signal(result)
                            
                            logger.info(f"Trade signal for {symbol}: {result.get('signal', {}).get('side')} "
                                      f"(Confidence: {result.get('signal', {}).get('confidence', 0):.2f})")
                        return result
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                        return None
                
                results = process_coins_parallel(
                    coins=top_coins,
                    process_func=process_coin,
                    max_workers=max_workers,
                    batch_size=batch_size,
                    rate_limit=rate_limit
                )
                results = [r for r in results if r]
            else:
                # Sequential processing
                results = []
                for coin in top_coins:
                    symbol = coin["symbol"]
                    logger.info(f"Processing {symbol}...")
                    
                    try:
                        result = bot.process_symbol(symbol, coin, btc_price, equity)
                        if result:
                            results.append(result)
                            result["mode"] = trading_mode
                            
                            if discord_webhook and result.get("signal", {}).get("side") != "Hold":
                                from monitoring.alerting import send_discord_trade_signal
                                send_discord_trade_signal(discord_webhook, result, signal_type="signal")
                            
                            if notion_client and result.get("execution", {}).get("success"):
                                notion_client.log_signal(result)
                                notion_client.log_execution(result)
                            
                            if discord_webhook and result.get("execution", {}).get("success"):
                                from monitoring.alerting import send_discord_trade_signal
                                send_discord_trade_signal(discord_webhook, result, signal_type="execution")
                            
                            if api_client and result.get("execution", {}).get("success"):
                                api_client.send_signal(result)
                            
                            logger.info(f"Trade signal for {symbol}: {result.get('signal', {}).get('side')} "
                                      f"(Confidence: {result.get('signal', {}).get('confidence', 0):.2f})")
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                        continue
            
            logger.info(f"Processing complete. {len(results)} signals generated.")
            
            # Update last execution timestamp in state manager
            if global_state_manager:
                global_state_manager.update_last_execution()
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            # Set error status in state manager
            if global_state_manager:
                global_state_manager.set_status(BotStatus.ERROR, str(e))
            time.sleep(60)  # Wait before retrying
        
        # Sleep until next iteration
        logger.info(f"Waiting {loop_interval} seconds until next cycle...")
        time.sleep(loop_interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger = setup_logger()
        logger.info("Shutting down gracefully due to user interrupt...")
        # FIX #6: Use global state_manager instance (not a new one)
        try:
            if global_state_manager:
                global_state_manager.set_status(BotStatus.STOPPED)
        except Exception as shutdown_error:
            logger.warning(f"Failed to update BotStateManager during shutdown: {shutdown_error}")
    except Exception as e:
        logger = setup_logger()
        logger.error(f"Fatal error occurred: {e}", exc_info=True)
        # FIX #6: Use global state_manager instance (not a new one)
        try:
            if global_state_manager:
                global_state_manager.set_status(BotStatus.ERROR, str(e))
        except Exception as state_error:
            logger.warning(f"Failed to update BotStateManager with error status: {state_error}")
        raise

