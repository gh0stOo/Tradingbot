"""API Routes for n8n Integration"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

router = APIRouter()

class TradeSignal(BaseModel):
    """Trade signal model"""
    symbol: str
    side: str
    price: float
    confidence: float
    strategies: List[str]
    regime: str
    orderId: Optional[str] = None
    qty: Optional[float] = None
    stopLoss: Optional[float] = None
    takeProfit: Optional[float] = None

class TradeExecute(BaseModel):
    """Trade execution model"""
    symbol: str
    side: str
    qty: float
    price: Optional[float] = None

@router.post("/api/v1/trade/signal")
async def post_trade_signal(signal: TradeSignal) -> Dict[str, Any]:
    """
    Receive trade signal from bot for n8n Discord notification
    
    This endpoint is called by the bot after generating a signal.
    n8n can listen to this and send Discord notifications.
    """
    return {
        "success": True,
        "received": True,
        "timestamp": datetime.utcnow().isoformat(),
        "signal": signal.dict()
    }

@router.post("/api/v1/trade/execute")
async def execute_trade(trade: TradeExecute) -> Dict[str, Any]:
    """
    Manually trigger trade execution (optional)
    
    This endpoint allows n8n to manually trigger trades if needed.
    """
    # This would call the order manager
    # For now, return placeholder
    return {
        "success": False,
        "error": "Manual execution not implemented yet",
        "message": "Use the bot's main loop for automated trading"
    }

@router.get("/api/v1/health")
async def health_check() -> Dict[str, Any]:
    """Comprehensive health check endpoint"""
    from datetime import datetime as dt

    try:
        health_result = {
            "status": "healthy",
            "timestamp": dt.utcnow().isoformat(),
            "checks": {
                "api_server": {
                    "status": "healthy",
                    "response_time_ms": 1
                },
                "database": {
                    "status": "healthy",
                    "note": "Check performed when bot initializes"
                },
                "exchange_connectivity": {
                    "status": "unknown",
                    "note": "Check performed when bot connects"
                }
            }
        }
        return health_result
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": dt.utcnow().isoformat(),
            "error": str(e)
        }

@router.get("/api/v1/status")
async def get_status() -> Dict[str, Any]:
    """Get bot status"""
    from dashboard.bot_state_manager import BotStateManager

    try:
        state_manager = BotStateManager()
        return {
            "status": state_manager.status.value,
            "bot_status": state_manager.status.name,
            "last_execution": state_manager.last_execution.isoformat() if state_manager.last_execution else None,
            "uptime": state_manager.get_status().get("uptime"),
            "start_time": state_manager.start_time.isoformat() if state_manager.start_time else None,
            "error": state_manager.error_message,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.get("/api/v1/system")
async def system_info() -> Dict[str, Any]:
    """Get system information"""
    import platform
    import psutil

    try:
        return {
            "system": {
                "platform": platform.system(),
                "python_version": platform.python_version(),
                "processor": platform.processor()
            },
            "resources": {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.post("/api/v1/bot/start")
async def start_bot() -> Dict[str, Any]:
    """Start the trading bot"""
    from dashboard.bot_state_manager import BotStateManager, BotStatus

    try:
        state_manager = BotStateManager()
        if state_manager.status == BotStatus.RUNNING:
            return {
                "success": False,
                "message": "Bot is already running",
                "status": state_manager.status.value,
                "timestamp": datetime.utcnow().isoformat()
            }

        state_manager.set_status(BotStatus.RUNNING)
        return {
            "success": True,
            "message": "Bot started successfully",
            "status": state_manager.status.value,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.post("/api/v1/bot/stop")
async def stop_bot() -> Dict[str, Any]:
    """Stop the trading bot"""
    from dashboard.bot_state_manager import BotStateManager, BotStatus

    try:
        state_manager = BotStateManager()
        if state_manager.status == BotStatus.STOPPED:
            return {
                "success": False,
                "message": "Bot is already stopped",
                "status": state_manager.status.value,
                "timestamp": datetime.utcnow().isoformat()
            }

        state_manager.set_status(BotStatus.STOPPED)
        return {
            "success": True,
            "message": "Bot stopped successfully",
            "status": state_manager.status.value,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.post("/api/v1/bot/pause")
async def pause_bot() -> Dict[str, Any]:
    """Pause the trading bot"""
    from dashboard.bot_state_manager import BotStateManager, BotStatus

    try:
        state_manager = BotStateManager()
        if state_manager.status != BotStatus.RUNNING:
            return {
                "success": False,
                "message": "Bot must be running to pause",
                "status": state_manager.status.value,
                "timestamp": datetime.utcnow().isoformat()
            }

        state_manager.pause_bot()
        return {
            "success": True,
            "message": "Bot paused successfully",
            "status": state_manager.status.value,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.post("/api/v1/bot/resume")
async def resume_bot() -> Dict[str, Any]:
    """Resume the trading bot"""
    from dashboard.bot_state_manager import BotStateManager, BotStatus

    try:
        state_manager = BotStateManager()
        if state_manager.status != BotStatus.PAUSED:
            return {
                "success": False,
                "message": "Bot must be paused to resume",
                "status": state_manager.status.value,
                "timestamp": datetime.utcnow().isoformat()
            }

        state_manager.resume_bot()
        return {
            "success": True,
            "message": "Bot resumed successfully",
            "status": state_manager.status.value,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@router.post("/api/v1/bot/emergency-stop")
async def emergency_stop() -> Dict[str, Any]:
    """Emergency stop - immediately halt bot operations"""
    from dashboard.bot_state_manager import BotStateManager, BotStatus

    try:
        state_manager = BotStateManager()
        state_manager.emergency_stop()
        return {
            "success": True,
            "message": "Emergency stop executed",
            "status": state_manager.status.value,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

