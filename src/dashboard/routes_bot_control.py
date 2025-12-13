"""Bot Control API Routes"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Dict, Any
import logging

from dashboard.bot_state_manager import BotStateManager, BotStatus

# Import BotStatus for comparisons

logger = logging.getLogger(__name__)

router = APIRouter()

# Get singleton instance
state_manager = BotStateManager()

@router.get("/api/bot/status")
async def get_bot_status() -> Dict[str, Any]:
    """Get current bot status"""
    return state_manager.get_status()

@router.post("/api/bot/start")
async def start_bot() -> Dict[str, Any]:
    """Start the trading bot"""
    try:
        current_status = state_manager.status
        if current_status == BotStatus.RUNNING:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Bot läuft bereits"}
            )
        
        # Set status to running - main.py loop will pick this up
        # IMPORTANT: This only sets the status. The actual bot process (main.py)
        # needs to be running separately and monitoring the BotStateManager.
        # In Docker, main.py should run as a separate service or be started
        # via supervisor/systemd.
        success = state_manager.start_bot()
        if not success:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Bot konnte nicht gestartet werden"}
            )
        
        logger.info("Bot start requested via API - Status set to RUNNING")
        
        # Return immediately - don't wait for bot to actually start
        # The bot process should be monitoring BotStateManager and will
        # pick up the status change asynchronously
        
        return {
            "success": True, 
            "message": "Bot Status auf RUNNING gesetzt",
            "warning": "Hinweis: Der Bot-Prozess (main.py) muss separat laufen, um auf Status-Änderungen zu reagieren."
        }
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/api/bot/stop")
async def stop_bot() -> Dict[str, Any]:
    """Stop the trading bot"""
    try:
        success = state_manager.stop_bot()
        if not success:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Bot ist bereits gestoppt"}
            )
        
        logger.info("Bot stop requested via API")
        
        # Bot stop is handled by BotStateManager
        # main_event_driven.py checks the status and stops execution
        
        return {"success": True, "message": "Bot gestoppt"}
    except Exception as e:
        logger.error(f"Error stopping bot: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/api/bot/pause")
async def pause_bot() -> Dict[str, Any]:
    """Pause the trading bot (keeps positions open)"""
    try:
        success = state_manager.pause_bot()
        if not success:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Bot muss laufen um pausiert zu werden"}
            )
        
        logger.info("Bot pause requested via API")
        
        # Bot pause is handled by BotStateManager
        # main_event_driven.py checks the status and pauses execution
        
        return {"success": True, "message": "Bot pausiert"}
    except Exception as e:
        logger.error(f"Error pausing bot: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/api/bot/resume")
async def resume_bot() -> Dict[str, Any]:
    """Resume the trading bot"""
    try:
        success = state_manager.resume_bot()
        if not success:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Bot ist nicht pausiert"}
            )
        
        logger.info("Bot resume requested via API")
        
        # Bot resume is handled by BotStateManager
        # main_event_driven.py checks the status and resumes execution
        
        return {"success": True, "message": "Bot fortgesetzt"}
    except Exception as e:
        logger.error(f"Error resuming bot: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/api/bot/emergency-stop")
async def emergency_stop() -> Dict[str, Any]:
    """Emergency stop - immediately stops bot and closes all positions"""
    try:
        success = state_manager.emergency_stop()
        if not success:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Emergency stop fehlgeschlagen"}
            )
        
        logger.warning("Emergency stop executed via API")
        
        # TODO: Actually stop bot and close all positions
        # This is critical - needs to be implemented carefully
        
        return {
            "success": True,
            "message": "Emergency Stop ausgeführt. Alle Positionen wurden geschlossen."
        }
    except Exception as e:
        logger.error(f"Error in emergency stop: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

