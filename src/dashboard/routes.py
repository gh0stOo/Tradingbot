"""Dashboard API Routes"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional, Dict, Any
from dashboard.stats_calculator import StatsCalculator
from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize Jinja2 templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Initialize stats calculator
# Default path, can be overridden
db_path = os.getenv("TRADING_DB_PATH", "data/trading.db")
stats_calc = StatsCalculator(db_path)

@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Dashboard homepage"""
    return templates.TemplateResponse("dashboard_new.html", {"request": request})

@router.get("/api/dashboard/stats")
async def get_all_stats(
    days: Optional[int] = Query(None, description="Filter by number of days")
) -> Dict[str, Any]:
    """
    Get all trading statistics
    
    Args:
        days: Optional filter by days (None = all time)
        
    Returns:
        Dictionary with all statistics
    """
    try:
        stats = stats_calc.calculate_stats(days=days)
        
        # Add time-filtered stats
        stats_30d = stats_calc.calculate_stats(days=30)
        stats_7d = stats_calc.calculate_stats(days=7)
        
        return {
            "allTime": stats,
            "last30Days": stats_30d,
            "last7Days": stats_7d
        }
    except Exception as e:
        logger.error(f"Error calculating stats: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Error calculating stats: {str(e)}"}
        )

@router.get("/api/dashboard/stats/daily")
async def get_daily_stats(
    days: int = Query(30, description="Number of days to retrieve")
) -> Dict[str, Any]:
    """Get daily performance statistics"""
    try:
        daily_perf = stats_calc.get_daily_performance(days=days)
        return {
            "dailyPerformance": daily_perf,
            "days": days
        }
    except Exception as e:
        logger.error(f"Error calculating daily stats: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Error calculating daily stats: {str(e)}"}
        )

@router.get("/api/dashboard/stats/weekly")
async def get_weekly_stats(
    weeks: int = Query(12, description="Number of weeks to retrieve")
) -> Dict[str, Any]:
    """Get weekly performance statistics"""
    try:
        weekly_perf = stats_calc.get_weekly_performance(weeks=weeks)
        return {
            "weeklyPerformance": weekly_perf,
            "weeks": weeks
        }
    except Exception as e:
        logger.error(f"Error calculating weekly stats: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Error calculating weekly stats: {str(e)}"}
        )

@router.get("/api/dashboard/stats/monthly")
async def get_monthly_stats(
    months: int = Query(12, description="Number of months to retrieve")
) -> Dict[str, Any]:
    """Get monthly performance statistics"""
    try:
        monthly_perf = stats_calc.get_monthly_performance(months=months)
        return {
            "monthlyPerformance": monthly_perf,
            "months": months
        }
    except Exception as e:
        logger.error(f"Error calculating monthly stats: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Error calculating monthly stats: {str(e)}"}
        )

@router.get("/api/dashboard/trades")
async def get_trades(
    days: Optional[int] = Query(None, description="Filter by number of days (None = all)"),
    limit: Optional[int] = Query(100, description="Maximum number of trades to return")
) -> Dict[str, Any]:
    """
    Get all trades with analysis data
    
    Args:
        days: Optional number of days to filter (None = all trades)
        limit: Maximum number of trades to return
        
    Returns:
        Dictionary with trades and their indicators
    """
    try:
        trades = stats_calc.get_all_trades(days=days)
        
        # Limit results
        if limit:
            trades = trades[:limit]
        
        # Fetch indicators for each trade
        trades_with_indicators = []
        conn = None
        try:
            conn = stats_calc._get_db_connection()
            
            for trade in trades:
                trade_id = trade.get('id')
                
                # Get indicators for this trade
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM indicators WHERE trade_id = ?
                """, (trade_id,))
                indicator_row = cursor.fetchone()
                
                indicators = {}
                if indicator_row:
                    indicators = dict(indicator_row)
                
                # Get market context for this trade
                cursor.execute("""
                    SELECT * FROM market_context WHERE trade_id = ?
                """, (trade_id,))
                context_row = cursor.fetchone()
                
                market_context = {}
                if context_row:
                    market_context = dict(context_row)
                
                trade_with_data = {
                    **trade,
                    "indicators": indicators,
                    "marketContext": market_context
                }
                trades_with_indicators.append(trade_with_data)
        finally:
            if conn:
                conn.close()
        
        return {
            "trades": trades_with_indicators,
            "count": len(trades_with_indicators),
            "filterDays": days,
            "limit": limit
        }
    except Exception as e:
        logger.error(f"Error fetching trades: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Error fetching trades: {str(e)}", "trades": [], "count": 0}
        )

@router.get("/bot-control", response_class=HTMLResponse)
async def bot_control_page(request: Request):
    """Bot Control page"""
    return templates.TemplateResponse("bot-control_new.html", {"request": request})

@router.get("/training", response_class=HTMLResponse)
async def training_page(request: Request):
    """Training page"""
    return templates.TemplateResponse("training_new.html", {"request": request})

@router.get("/backtesting", response_class=HTMLResponse)
async def backtesting_page(request: Request):
    """Backtesting page"""
    return templates.TemplateResponse("backtesting_new.html", {"request": request})

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings management page"""
    return templates.TemplateResponse("settings_new.html", {"request": request})

@router.get("/events", response_class=HTMLResponse)
async def events_page(request: Request):
    """Operations events monitoring page"""
    return templates.TemplateResponse("events_new.html", {"request": request})

@router.get("/live-trading", response_class=HTMLResponse)
async def live_trading_page():
    """Live Trading page"""
    html_file = Path(__file__).parent / "templates" / "live-trading.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding='utf-8'), status_code=200)
    return HTMLResponse(content="<h1>Live Trading</h1><p>Page not found</p>", status_code=200)

@router.get("/trade-history", response_class=HTMLResponse)
async def trade_history_page():
    """Trade History page"""
    html_file = Path(__file__).parent / "templates" / "trade-history.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding='utf-8'), status_code=200)
    return HTMLResponse(content="<h1>Trade History</h1><p>Page not found</p>", status_code=200)

@router.get("/api/positions/active")
async def get_active_positions() -> Dict[str, Any]:
    """Get all active/open positions"""
    try:
        # Try to get positions from database via stats calculator
        trades = stats_calc.get_all_trades(days=None)
        open_positions = [
            trade for trade in trades 
            if trade.get('exit_time') is None
        ]
        
        # Format positions for frontend
        positions = []
        for trade in open_positions:
            positions.append({
                "trade_id": trade.get('id'),
                "symbol": trade.get('symbol'),
                "side": trade.get('side'),
                "entry_price": trade.get('entry_price'),
                "quantity": trade.get('quantity'),
                "timestamp": trade.get('timestamp'),
                "stop_loss": trade.get('stop_loss'),
                "take_profit": trade.get('take_profit'),
                "unrealized_pnl": trade.get('unrealized_pnl', 0),
                "trading_mode": trade.get('trading_mode', 'PAPER')
            })
        
        return {
            "positions": positions,
            "count": len(positions)
        }
    except Exception as e:
        logger.error(f"Error fetching active positions: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e), "positions": [], "count": 0}
        )

@router.post("/api/positions/{position_id}/close")
async def close_position(position_id: int) -> Dict[str, Any]:
    """Close a position manually"""
    try:
        # NOTE: Manual position closure via API not yet implemented
        # Would require integration with PositionManager/OrderManager

        logger.warning(f"Position {position_id} close requested via API - NOT IMPLEMENTED")

        return JSONResponse(
            status_code=501,
            content={
                "success": False,
                "error": "Manual position closure via API not yet implemented",
                "message": "Use trading bot controls instead"
            }
        )
    except Exception as e:
        logger.error(f"Error closing position {position_id}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.get("/api/signals/recent")
async def get_recent_signals(limit: int = 50) -> Dict[str, Any]:
    """Get recent trading signals"""
    try:
        # NOTE: Fetch signals from database
        # Requires integration with signal logging system
        signals = []

        try:
            # Attempt to get signals from database if available
            # This would require access to the signal event log
            # For now, return empty until proper logging is implemented
            pass
        except Exception as e:
            logger.warning(f"Could not fetch signals from database: {e}")

        return {
            "signals": signals,
            "count": len(signals)
        }
    except Exception as e:
        logger.error(f"Error fetching signals: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Error fetching signals: {str(e)}", "signals": [], "count": 0}
        )

@router.get("/api/performance/live")
async def get_live_performance() -> Dict[str, Any]:
    """Get live performance metrics"""
    try:
        stats = stats_calc.calculate_stats(days=1)  # Today
        stats_7d = stats_calc.calculate_stats(days=7)
        stats_30d = stats_calc.calculate_stats(days=30)
        
        return {
            "todayPnL": stats.get("totalPnL", 0),
            "weekPnL": stats_7d.get("totalPnL", 0),
            "monthPnL": stats_30d.get("totalPnL", 0),
            "todayWinRate": stats.get("winRate", 0),
            "weekWinRate": stats_7d.get("winRate", 0),
            "monthWinRate": stats_30d.get("winRate", 0)
        }
    except Exception as e:
        logger.error(f"Error calculating performance: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Error calculating performance: {str(e)}"}
        )

@router.get("/api/dashboard/trades/export")
async def export_trades(
    days: Optional[int] = Query(None, description="Filter by number of days (None = all)")
) -> JSONResponse:
    """
    Export trades as JSON
    
    Args:
        days: Optional number of days to filter (None = all trades)
        
    Returns:
        JSON response with all trades
    """
    try:
        trades = stats_calc.get_all_trades(days=days)
        
        # Get export timestamp
        conn = None
        exported_at = None
        try:
            conn = stats_calc._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT datetime('now')")
            exported_at = cursor.fetchone()[0]
        finally:
            if conn:
                conn.close()
        
        return JSONResponse(content={
            "trades": trades,
            "count": len(trades),
            "filterDays": days,
            "exportedAt": exported_at
        })
    except Exception as e:
        logger.error(f"Error exporting trades: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

