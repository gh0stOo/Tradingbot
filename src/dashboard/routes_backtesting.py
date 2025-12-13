"""Backtesting API Routes"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()

# Backtest State (in production, use database)
backtests = {}
backtest_counter = 0

class BacktestRequest(BaseModel):
    start_date: str
    end_date: str
    symbols: Optional[List[str]] = None
    initial_equity: float = 10000.0

@router.post("/api/backtesting/run")
async def run_backtest(request: BacktestRequest) -> Dict[str, Any]:
    """Start a new backtest"""
    try:
        global backtest_counter
        backtest_counter += 1
        backtest_id = f"bt_{backtest_counter}_{int(datetime.utcnow().timestamp())}"
        
        # Parse dates
        start_date = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
        
        backtests[backtest_id] = {
            "id": backtest_id,
            "status": "running",  # running, completed, error
            "progress": 0,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "symbols": request.symbols or [],
            "initial_equity": request.initial_equity,
            "created_at": datetime.utcnow().isoformat(),
            "results": None
        }
        
        logger.info(f"Backtest {backtest_id} started via API")
        
        # Run actual backtest using EventBacktest
        import asyncio
        import threading
        asyncio.create_task(_run_actual_backtest(backtest_id, start_date, end_date, request.symbols, request.initial_equity))
        
        return {
            "success": True,
            "backtest_id": backtest_id,
            "message": "Backtest gestartet"
        }
    except Exception as e:
        logger.error(f"Error starting backtest: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/api/backtesting/list")
async def list_backtests() -> Dict[str, Any]:
    """List all backtests"""
    return {
        "backtests": list(backtests.values()),
        "count": len(backtests)
    }

@router.get("/api/backtesting/status/{backtest_id}")
async def get_backtest_status(backtest_id: str) -> Dict[str, Any]:
    """Get backtest status"""
    if backtest_id not in backtests:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Backtest nicht gefunden"}
        )
    
    backtest = backtests[backtest_id]
    result = {
        "id": backtest["id"],
        "status": backtest["status"],
        "progress": backtest["progress"],
        "start_date": backtest["start_date"],
        "end_date": backtest["end_date"],
        "created_at": backtest["created_at"]
    }
    
    if backtest["status"] == "completed" and backtest["results"]:
        result["results"] = backtest["results"]
    
    return result

@router.get("/api/backtesting/results/{backtest_id}")
async def get_backtest_results(backtest_id: str) -> Dict[str, Any]:
    """Get backtest results"""
    if backtest_id not in backtests:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Backtest nicht gefunden"}
        )
    
    backtest = backtests[backtest_id]
    
    if backtest["status"] != "completed":
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Backtest noch nicht abgeschlossen"}
        )
    
    if not backtest["results"]:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Backtest Ergebnisse nicht verfügbar"}
        )
    
    return backtest["results"]

@router.delete("/api/backtesting/cancel/{backtest_id}")
async def cancel_backtest(backtest_id: str) -> Dict[str, Any]:
    """Cancel a running backtest"""
    if backtest_id not in backtests:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Backtest nicht gefunden"}
        )
    
    backtest = backtests[backtest_id]
    
    if backtest["status"] != "running":
        return {"success": False, "error": "Backtest läuft nicht"}
    
    backtest["status"] = "cancelled"
    logger.info(f"Backtest {backtest_id} cancelled")
    
    return {"success": True, "message": "Backtest abgebrochen"}

async def _run_actual_backtest(backtest_id: str, start_date: datetime, end_date: datetime, symbols: Optional[List[str]], initial_equity: float):
    """Run actual backtest using EventBacktest"""
    import asyncio
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    try:
        backtest = backtests[backtest_id]
        backtest["progress"] = 10
        
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
        
        backtest["progress"] = 30
        
        # Create backtest instance
        backtest_engine = EventBacktest(
            trading_state=trading_state,
            risk_engine=risk_engine,
            strategy_allocator=strategy_allocator,
            order_executor=order_executor,
            strategies=strategies,
            config=config,
            market_data=market_data,
            initial_equity=float(initial_equity)
        )
        
        backtest["progress"] = 50
        
        # Run backtest in thread (to not block event loop)
        def run_in_thread():
            try:
                # Get symbols if not provided
                test_symbols = symbols or ["BTCUSDT"]
                
                # Run backtest
                results = backtest_engine.run(
                    symbols=test_symbols,
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Update backtest with results
                backtest["progress"] = 100
                backtest["status"] = "completed"
                backtest["results"] = {
                    "totalPnL": results.get("total_return", 0) * initial_equity,
                    "totalReturn": results.get("total_return_pct", 0),
                    "winRate": 0,  # Would need to calculate from trades
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
            except Exception as e:
                logger.error(f"Error running backtest {backtest_id}: {e}", exc_info=True)
                backtest["status"] = "error"
                backtest["error"] = str(e)
        
        # Run in background thread
        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()
        
        # Wait for completion (with timeout)
        thread.join(timeout=300)  # 5 minutes timeout
        
        if thread.is_alive():
            backtest["status"] = "error"
            backtest["error"] = "Backtest timeout"
        
    except Exception as e:
        logger.error(f"Error in backtest {backtest_id}: {e}", exc_info=True)
        if backtest_id in backtests:
            backtests[backtest_id]["status"] = "error"
            backtests[backtest_id]["error"] = str(e)

