"""Backtesting API Routes - SQLite-based for Docker compatibility (FIXED VERSION)"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel
import logging
import uuid
import os
import json
import pandas as pd

from data.database import Database

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize database for backtest state
db_path = os.getenv("TRADING_DB_PATH", "data/trading.db")
backtest_db = Database(db_path)

class BacktestRequest(BaseModel):
    start_date: str
    end_date: str
    symbols: Optional[List[str]] = None
    initial_equity: float = 10000.0

@router.post("/api/backtesting/run")
async def run_backtest(request: BacktestRequest) -> Dict[str, Any]:
    """Start a new backtest - stores state in SQLite"""
    try:
        # Generate backtest ID
        backtest_id = f"bt_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        # Parse dates
        start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
        
        # Store in SQLite
        symbols_json = json.dumps(request.symbols) if request.symbols else None
        backtest_db.create_backtest(
            backtest_id=backtest_id,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            symbols=symbols_json,
            initial_equity=request.initial_equity
        )
        
        logger.info(f"Backtest {backtest_id} started via API - stored in SQLite")
        
        # Run actual backtest using EventBacktest (in background thread)
        import threading
        thread = threading.Thread(
            target=_run_actual_backtest,
            args=(backtest_id, start_date, end_date, request.symbols, request.initial_equity),
            daemon=True
        )
        thread.start()
        
        return {
            "success": True,
            "backtest_id": backtest_id,
            "message": "Backtest gestartet",
            "status": "running"
        }
    except Exception as e:
        logger.error(f"Error starting backtest: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/api/backtesting/list")
async def list_backtests() -> Dict[str, Any]:
    """List all backtests from SQLite"""
    try:
        backtests_list = backtest_db.list_backtests(limit=100)
        # Parse JSON fields
        for bt in backtests_list:
            if bt.get("symbols"):
                try:
                    bt["symbols"] = json.loads(bt["symbols"])
                except:
                    bt["symbols"] = []
            if bt.get("results"):
                try:
                    bt["results"] = json.loads(bt["results"])
                except:
                    pass
        
        return {
            "backtests": backtests_list,
            "count": len(backtests_list)
        }
    except Exception as e:
        logger.error(f"Error listing backtests: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/api/backtesting/status/{backtest_id}")
async def get_backtest_status(backtest_id: str) -> Dict[str, Any]:
    """Get backtest status from SQLite"""
    try:
        backtest = backtest_db.get_backtest(backtest_id)
        if not backtest:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Backtest nicht gefunden"}
            )
        
        # Parse JSON fields
        if backtest.get("symbols"):
            try:
                backtest["symbols"] = json.loads(backtest["symbols"])
            except:
                backtest["symbols"] = []
        
        result = {
            "id": backtest["id"],
            "status": backtest["status"],
            "progress": backtest["progress"],
            "start_date": backtest["start_date"],
            "end_date": backtest["end_date"],
            "created_at": backtest["created_at"],
            "symbols": backtest.get("symbols", []),
            "initial_equity": backtest.get("initial_equity", 10000.0)
        }
        
        if backtest["status"] == "completed" and backtest.get("results"):
            try:
                result["results"] = json.loads(backtest["results"])
            except:
                result["results"] = None
        
        if backtest.get("error"):
            result["error"] = backtest["error"]
            result["error_type"] = backtest.get("error_type")
        
        return result
    except Exception as e:
        logger.error(f"Error getting backtest status: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/api/backtesting/results/{backtest_id}")
async def get_backtest_results(backtest_id: str) -> Dict[str, Any]:
    """Get backtest results from SQLite"""
    try:
        backtest = backtest_db.get_backtest(backtest_id)
        if not backtest:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Backtest nicht gefunden"}
            )
        
        if backtest["status"] != "completed":
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Backtest noch nicht abgeschlossen", "status": backtest["status"]}
            )
        
        if not backtest.get("results"):
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Backtest Ergebnisse nicht verfügbar"}
            )
        
        # Parse results JSON
        try:
            results = json.loads(backtest["results"])
            return results
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing backtest results JSON: {e}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Fehler beim Parsen der Ergebnisse"}
            )
    except Exception as e:
        logger.error(f"Error getting backtest results: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.delete("/api/backtesting/cancel/{backtest_id}")
async def cancel_backtest(backtest_id: str) -> Dict[str, Any]:
    """Cancel a running backtest"""
    try:
        backtest = backtest_db.get_backtest(backtest_id)
        if not backtest:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Backtest nicht gefunden"}
            )
        
        if backtest["status"] != "running":
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Backtest läuft nicht", "status": backtest["status"]}
            )
        
        backtest_db.update_backtest_status(backtest_id, "cancelled")
        logger.info(f"Backtest {backtest_id} cancelled")
        
        return {"success": True, "message": "Backtest abgebrochen"}
    except Exception as e:
        logger.error(f"Error cancelling backtest: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

def _fetch_from_binance_api(symbols: List[str], start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
    """
    Fetch historical klines from Binance API
    
    Args:
        symbols: List of trading symbols
        start_date: Start date
        end_date: End date
    
    Returns:
        List of kline dictionaries
    """
    import requests
    from datetime import timedelta
    
    historical_data_list = []
    
    for symbol in symbols:
        try:
            # Binance API endpoint
            base_url = "https://api.binance.com/api/v3/klines"
            
            # Convert dates to milliseconds
            start_ms = int(start_date.timestamp() * 1000)
            end_ms = int(end_date.timestamp() * 1000)
            
            # Binance limit: 1000 klines per request
            # Fetch in batches
            current_start = start_ms
            batch_size = 1000 * 60 * 1000  # 1000 minutes in milliseconds
            
            while current_start < end_ms:
                current_end = min(current_start + batch_size, end_ms)
                
                params = {
                    "symbol": symbol,
                    "interval": "1m",  # 1 minute
                    "startTime": current_start,
                    "endTime": current_end,
                    "limit": 1000
                }
                
                response = requests.get(base_url, params=params, timeout=10)
                response.raise_for_status()
                
                klines = response.json()
                
                for kline in klines:
                    historical_data_list.append({
                        "timestamp": datetime.fromtimestamp(kline[0] / 1000).isoformat(),
                        "symbol": symbol,
                        "open": float(kline[1]),
                        "high": float(kline[2]),
                        "low": float(kline[3]),
                        "close": float(kline[4]),
                        "volume": float(kline[5])
                    })
                
                # Move to next batch
                if klines:
                    current_start = klines[-1][0] + 60000  # Next minute
                else:
                    break
                
                # Rate limiting
                import time
                time.sleep(0.1)
            
            logger.info(f"Fetched {len([d for d in historical_data_list if d['symbol'] == symbol])} klines from Binance for {symbol}")
            
        except Exception as e:
            logger.error(f"Error fetching from Binance API for {symbol}: {e}")
            continue
    
    return historical_data_list


def _save_klines_to_db(db, historical_data_list: List[Dict[str, Any]]) -> None:
    """
    Save klines to database for future use
    
    Args:
        db: Database instance
        historical_data_list: List of kline dictionaries
    """
    try:
        for kline in historical_data_list:
            db.execute(
                """INSERT OR IGNORE INTO klines_archive 
                   (symbol, timestamp, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    kline["symbol"],
                    kline["timestamp"],
                    kline["open"],
                    kline["high"],
                    kline["low"],
                    kline["close"],
                    kline["volume"]
                )
            )
        db.flush_writes(timeout=30.0)
        logger.info(f"Saved {len(historical_data_list)} klines to database")
    except Exception as e:
        logger.warning(f"Error saving klines to database: {e}")


def _run_actual_backtest(backtest_id: str, start_date: datetime, end_date: datetime, symbols: Optional[List[str]], initial_equity: float):
    """Run actual backtest using EventBacktest - updates SQLite"""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    try:
        # Update progress in SQLite
        backtest_db.update_backtest_status(backtest_id, "running", progress=10)
        
        # Import required modules
        from utils.config_loader import ConfigLoader
        from backtesting.event_backtest import EventBacktest
        from integrations.bybit import BybitClient
        from trading.market_data import MarketData
        from core.trading_state import TradingState
        from core.risk_engine import RiskEngine
        from core.strategy_allocator import StrategyAllocator
        from core.order_executor import OrderExecutor
        from strategies.volatility_expansion import VolatilityExpansionStrategy
        from strategies.mean_reversion import MeanReversionStrategy
        from strategies.trend_continuation import TrendContinuationStrategy
        
        # Load config
        config_loader = ConfigLoader()
        config = config_loader.config
        
        backtest_db.update_backtest_status(backtest_id, "running", progress=20)
        
        # Initialize components
        trading_state = TradingState(initial_cash=float(initial_equity))
        trading_state.enable_trading()
        
        risk_engine = RiskEngine(config, trading_state)
        strategy_allocator = StrategyAllocator(config, trading_state)
        
        # Create Bybit client (for market data)
        bybit_config = config.get("bybit", {})
        market_data_client = BybitClient(
            api_key=bybit_config.get("testnet_api_key", ""),
            api_secret=bybit_config.get("testnet_api_secret", ""),
            testnet=True
        )
        market_data = MarketData(market_data_client)
        
        order_executor = OrderExecutor(trading_state, None, "PAPER", config)
        
        # Initialize strategies
        strategies = [
            VolatilityExpansionStrategy(config),
            MeanReversionStrategy(config),
            TrendContinuationStrategy(config),
        ]
        
        backtest_db.update_backtest_status(backtest_id, "running", progress=30)
        
        # Progress callback for SQLite updates
        def progress_callback(progress: int, message: str):
            """Update backtest progress in SQLite"""
            try:
                backtest_db.update_backtest_status(backtest_id, "running", progress=progress)
                logger.debug(f"Backtest {backtest_id} progress: {progress}% - {message}")
            except Exception as e:
                logger.debug(f"Could not update progress: {e}")
        
        # Create backtest instance with progress callback
        backtest_engine = EventBacktest(
            trading_state=trading_state,
            risk_engine=risk_engine,
            strategy_allocator=strategy_allocator,
            order_executor=order_executor,
            strategies=strategies,
            config=config,
            market_data=market_data,
            initial_equity=float(initial_equity),
            progress_callback=progress_callback
        )
        
        backtest_db.update_backtest_status(backtest_id, "running", progress=50)
        
        # Get symbols if not provided
        test_symbols = symbols or ["BTCUSDT"]
        
        # Fetch historical data from database
        backtest_db.update_backtest_status(backtest_id, "running", progress=60)
        logger.info(f"Fetching historical data for {test_symbols} from {start_date} to {end_date}")
        
        # Fetch klines from database first, fallback to Binance API if not available
        historical_data_list = []
        for symbol in test_symbols:
            try:
                cursor = backtest_db.execute(
                    """SELECT timestamp, open, high, low, close, volume 
                       FROM klines_archive 
                       WHERE symbol = ? AND timestamp >= ? AND timestamp <= ?
                       ORDER BY timestamp""",
                    (symbol, start_date.isoformat(), end_date.isoformat())
                )
                rows = cursor.fetchall()
                
                for row in rows:
                    historical_data_list.append({
                        "timestamp": row["timestamp"],
                        "symbol": symbol,
                        "open": row["open"],
                        "high": row["high"],
                        "low": row["low"],
                        "close": row["close"],
                        "volume": row["volume"]
                    })
            except Exception as e:
                logger.warning(f"Error fetching historical data from DB for {symbol}: {e}")
        
        # If no data in database, fetch from Binance API
        if not historical_data_list:
            logger.info(f"No data in database, fetching from Binance API for {test_symbols}")
            try:
                historical_data_list = _fetch_from_binance_api(test_symbols, start_date, end_date)
                if historical_data_list:
                    logger.info(f"Fetched {len(historical_data_list)} klines from Binance API")
                    # Optionally save to database for future use
                    _save_klines_to_db(backtest_db, historical_data_list)
                else:
                    error_msg = f"No historical data found for symbols {test_symbols} in date range (tried DB and Binance API)"
                    logger.error(error_msg)
                    backtest_db.update_backtest_status(
                        backtest_id,
                        "error",
                        error=error_msg,
                        error_type="DataNotFoundError"
                    )
                    return
            except Exception as e:
                error_msg = f"Error fetching from Binance API: {str(e)}"
                logger.error(error_msg)
                backtest_db.update_backtest_status(
                    backtest_id,
                    "error",
                    error=error_msg,
                    error_type="APIError"
                )
                return
        
        # Convert to DataFrame
        historical_data = pd.DataFrame(historical_data_list)
        backtest_db.update_backtest_status(backtest_id, "running", progress=70)
        
        # Run backtest
        try:
            logger.info(f"Running backtest for {len(historical_data)} data points")
            
            # Use run_backtest() method which expects historical_data DataFrame
            results = backtest_engine.run_backtest(
                historical_data=historical_data,
                strategies=strategies,
                risk_config=config.get("risk", {}),
                start_date=start_date,
                end_date=end_date
            )
            
            # Format results for storage
            win_rate = results.get("win_rate", 0.0)
            win_rate_pct = results.get("win_rate_pct", 0.0)
            
            results_dict = {
                "totalPnL": results.get("total_return", 0) * initial_equity,
                "totalReturn": results.get("total_return_pct", 0),
                "winRate": win_rate,
                "winRatePct": win_rate_pct,
                "totalTrades": results.get("num_trades", 0),
                "maxDrawdown": results.get("max_drawdown_pct", 0),
                "profitFactor": results.get("profit_factor", 0),
                "expectancy": results.get("expectancy", 0),
                "tailLoss95": results.get("tail_loss_95", 0),
                "tailLoss99": results.get("tail_loss_99", 0),
                "timeToRecovery": results.get("time_to_recovery_hours", 0),
                "tradesPerDay": results.get("trades_per_day", 0),
                "equityCurve": results.get("equity_curve", [])
            }
            
            # Store results in SQLite
            # Convert Timestamp and Decimal objects to JSON-serializable types
            def json_serializer(obj):
                """Custom JSON serializer for Timestamp and Decimal objects"""
                from decimal import Decimal
                if isinstance(obj, pd.Timestamp):
                    return obj.isoformat()
                elif isinstance(obj, Decimal):
                    return float(obj)
                elif isinstance(obj, (datetime, pd.Timestamp)):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            
            results_json = json.dumps(results_dict, default=json_serializer)
            backtest_db.update_backtest_status(
                backtest_id, 
                "completed", 
                progress=100,
                results=results_json
            )
            logger.info(f"Backtest {backtest_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error running backtest {backtest_id}: {e}", exc_info=True)
            error_details = json.dumps({
                "message": str(e),
                "type": type(e).__name__,
                "traceback": None
            })
            backtest_db.update_backtest_status(
                backtest_id,
                "error",
                error=str(e),
                error_type=type(e).__name__,
                error_details=error_details
            )
        
    except Exception as e:
        logger.error(f"Error in backtest {backtest_id}: {e}", exc_info=True)
        error_details = json.dumps({
            "message": str(e),
            "type": type(e).__name__,
            "traceback": None
        })
        backtest_db.update_backtest_status(
            backtest_id,
            "error",
            error=str(e),
            error_type=type(e).__name__,
            error_details=error_details
        )

