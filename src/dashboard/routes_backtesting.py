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
        
        # TODO: Actually run backtest
        # This would need to integrate with BacktestEngine
        
        # Simulate backtest completion (for now)
        import asyncio
        asyncio.create_task(_simulate_backtest(backtest_id))
        
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

async def _simulate_backtest(backtest_id: str):
    """Simulate backtest progress (for development)"""
    import asyncio
    backtest = backtests[backtest_id]
    for i in range(100):
        await asyncio.sleep(0.2)
        backtest["progress"] = i + 1
        if backtest["status"] != "running":
            break
    
    if backtest["status"] == "running":
        backtest["status"] = "completed"
        backtest["results"] = {
            "totalPnL": 1250.50,
            "winRate": 65.5,
            "totalTrades": 142,
            "winningTrades": 93,
            "losingTrades": 49,
            "sharpeRatio": 1.85,
            "maxDrawdown": 8.5,
            "profitFactor": 2.1,
            "averageWin": 45.20,
            "averageLoss": -22.10
        }

