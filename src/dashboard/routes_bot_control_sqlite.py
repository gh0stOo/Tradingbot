"""Bot Control API Routes - SQLite-based for Docker compatibility"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Dict, Any
import logging
import os
from datetime import datetime, timezone

from data.database import Database
from dashboard.audit_trail import get_audit_trail, AuditAction

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize database for bot control and audit trail
db_path = os.getenv("TRADING_DB_PATH", "data/trading.db")
bot_db = Database(db_path)
audit_trail = get_audit_trail()

@router.get("/api/v1/bot/status")
async def get_bot_status() -> Dict[str, Any]:
    """Get current bot status from SQLite"""
    try:
        control = bot_db.get_bot_control()
        if not control:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Bot control state not found in database"}
            )
        
        # Calculate uptime if running
        uptime_seconds = 0
        if control["actual_state"] == "running" and control["last_heartbeat"]:
            try:
                last_heartbeat = datetime.fromisoformat(control["last_heartbeat"].replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                last_hb = datetime.fromisoformat(control["last_heartbeat"].replace('Z', '+00:00'))
                if last_hb.tzinfo is None:
                    last_hb = last_hb.replace(tzinfo=timezone.utc)
                uptime_seconds = int((now - last_hb).total_seconds())
            except:
                pass
        
        # Format uptime
        uptime_str = "0s"
        if uptime_seconds < 60:
            uptime_str = f"{uptime_seconds}s"
        elif uptime_seconds < 3600:
            minutes = uptime_seconds // 60
            uptime_str = f"{minutes}m"
        else:
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            uptime_str = f"{hours}h {minutes}m"
        
        return {
            "status": control["actual_state"],
            "desired_state": control["desired_state"],
            "uptime": uptime_str,
            "last_heartbeat": control["last_heartbeat"],
            "last_error": control["last_error"],
            "updated_at": control["updated_at"]
        }
    except Exception as e:
        logger.error(f"Error getting bot status: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/api/v1/bot/start")
async def start_bot() -> Dict[str, Any]:
    """Start the trading bot - writes desired_state to SQLite"""
    try:
        control = bot_db.get_bot_control()
        if not control:
            # Log failed attempt to audit trail
            audit_trail.log(
                action=AuditAction.BOT_STARTED,
                entity_type="bot_control",
                entity_key="bot_state",
                old_value=None,
                new_value="running",
                result="failed",
                error_message="Bot control state not found in database"
            )
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Bot control state not found in database"}
            )

        if control["actual_state"] == "running":
            # Log failed attempt (already running)
            audit_trail.log(
                action=AuditAction.BOT_STARTED,
                entity_type="bot_control",
                entity_key="bot_state",
                old_value=control["actual_state"],
                new_value="running",
                result="failed",
                error_message="Bot läuft bereits"
            )
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Bot läuft bereits"}
            )

        # Set desired_state to 'running' in SQLite
        old_state = control["actual_state"]
        bot_db.set_bot_desired_state("running")
        bot_db.update_bot_actual_state("running")
        logger.info("Bot start requested via API - desired_state set to 'running' in SQLite")

        # Log successful start attempt
        audit_trail.log(
            action=AuditAction.BOT_STARTED,
            entity_type="bot_control",
            entity_key="bot_state",
            old_value=old_state,
            new_value="running",
            result="success"
        )

        return {
            "success": True,
            "message": "Bot-Start angefordert. Worker wird Status aus SQLite lesen.",
            "desired_state": "running",
            "note": "Der Bot-Worker (main.py) liest desired_state periodisch aus SQLite und startet den Bot."
        }
    except Exception as e:
        # Log exception to audit trail
        audit_trail.log(
            action=AuditAction.BOT_STARTED,
            entity_type="bot_control",
            entity_key="bot_state",
            old_value=None,
            new_value="running",
            result="failed",
            error_message=str(e)
        )
        logger.error(f"Error starting bot: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/api/v1/bot/stop")
async def stop_bot() -> Dict[str, Any]:
    """Stop the trading bot - writes desired_state to SQLite"""
    try:
        control = bot_db.get_bot_control()
        if not control:
            # Log failed attempt
            audit_trail.log(
                action=AuditAction.BOT_STOPPED,
                entity_type="bot_control",
                entity_key="bot_state",
                old_value=None,
                new_value="stopped",
                result="failed",
                error_message="Bot control state not found in database"
            )
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Bot control state not found in database"}
            )

        if control["actual_state"] == "stopped":
            # Log failed attempt (already stopped)
            audit_trail.log(
                action=AuditAction.BOT_STOPPED,
                entity_type="bot_control",
                entity_key="bot_state",
                old_value=control["actual_state"],
                new_value="stopped",
                result="failed",
                error_message="Bot ist bereits gestoppt"
            )
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Bot ist bereits gestoppt"}
            )

        # Set desired_state to 'stopped' in SQLite
        old_state = control["actual_state"]
        bot_db.set_bot_desired_state("stopped")
        bot_db.update_bot_actual_state("stopped")
        logger.info("Bot stop requested via API - desired_state set to 'stopped' in SQLite")

        # Log successful stop
        audit_trail.log(
            action=AuditAction.BOT_STOPPED,
            entity_type="bot_control",
            entity_key="bot_state",
            old_value=old_state,
            new_value="stopped",
            result="success"
        )

        return {
            "success": True,
            "message": "Bot-Stopp angefordert. Worker wird Status aus SQLite lesen.",
            "desired_state": "stopped"
        }
    except Exception as e:
        # Log exception
        audit_trail.log(
            action=AuditAction.BOT_STOPPED,
            entity_type="bot_control",
            entity_key="bot_state",
            old_value=None,
            new_value="stopped",
            result="failed",
            error_message=str(e)
        )
        logger.error(f"Error stopping bot: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/api/v1/bot/pause")
async def pause_bot() -> Dict[str, Any]:
    """Pause the trading bot - writes desired_state to SQLite"""
    try:
        control = bot_db.get_bot_control()
        if not control:
            # Log failed attempt
            audit_trail.log(
                action=AuditAction.BOT_PAUSED,
                entity_type="bot_control",
                entity_key="bot_state",
                old_value=None,
                new_value="paused",
                result="failed",
                error_message="Bot control state not found in database"
            )
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Bot control state not found in database"}
            )

        if control["actual_state"] != "running":
            # Log failed attempt (not running)
            audit_trail.log(
                action=AuditAction.BOT_PAUSED,
                entity_type="bot_control",
                entity_key="bot_state",
                old_value=control["actual_state"],
                new_value="paused",
                result="failed",
                error_message="Bot muss laufen um pausiert zu werden"
            )
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Bot muss laufen um pausiert zu werden"}
            )

        # Set desired_state to 'paused' in SQLite
        old_state = control["actual_state"]
        bot_db.set_bot_desired_state("paused")
        bot_db.update_bot_actual_state("paused")
        logger.info("Bot pause requested via API - desired_state set to 'paused' in SQLite")

        # Log successful pause
        audit_trail.log(
            action=AuditAction.BOT_PAUSED,
            entity_type="bot_control",
            entity_key="bot_state",
            old_value=old_state,
            new_value="paused",
            result="success"
        )

        return {
            "success": True,
            "message": "Bot-Pause angefordert. Worker wird Status aus SQLite lesen.",
            "desired_state": "paused"
        }
    except Exception as e:
        # Log exception
        audit_trail.log(
            action=AuditAction.BOT_PAUSED,
            entity_type="bot_control",
            entity_key="bot_state",
            old_value=None,
            new_value="paused",
            result="failed",
            error_message=str(e)
        )
        logger.error(f"Error pausing bot: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/api/v1/bot/resume")
async def resume_bot() -> Dict[str, Any]:
    """Resume the trading bot - writes desired_state to SQLite"""
    try:
        control = bot_db.get_bot_control()
        if not control:
            # Log failed attempt
            audit_trail.log(
                action=AuditAction.BOT_RESUMED,
                entity_type="bot_control",
                entity_key="bot_state",
                old_value=None,
                new_value="running",
                result="failed",
                error_message="Bot control state not found in database"
            )
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": "Bot control state not found in database"}
            )

        if control["actual_state"] != "paused":
            # Log failed attempt (not paused)
            audit_trail.log(
                action=AuditAction.BOT_RESUMED,
                entity_type="bot_control",
                entity_key="bot_state",
                old_value=control["actual_state"],
                new_value="running",
                result="failed",
                error_message="Bot ist nicht pausiert"
            )
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Bot ist nicht pausiert"}
            )

        # Set desired_state to 'running' in SQLite
        old_state = control["actual_state"]
        bot_db.set_bot_desired_state("running")
        bot_db.update_bot_actual_state("running")
        logger.info("Bot resume requested via API - desired_state set to 'running' in SQLite")

        # Log successful resume
        audit_trail.log(
            action=AuditAction.BOT_RESUMED,
            entity_type="bot_control",
            entity_key="bot_state",
            old_value=old_state,
            new_value="running",
            result="success"
        )

        return {
            "success": True,
            "message": "Bot-Fortsetzung angefordert. Worker wird Status aus SQLite lesen.",
            "desired_state": "running"
        }
    except Exception as e:
        # Log exception
        audit_trail.log(
            action=AuditAction.BOT_RESUMED,
            entity_type="bot_control",
            entity_key="bot_state",
            old_value=None,
            new_value="running",
            result="failed",
            error_message=str(e)
        )
        logger.error(f"Error resuming bot: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@router.post("/api/v1/bot/emergency-stop")
async def emergency_stop() -> Dict[str, Any]:
    """Emergency stop - immediately sets desired_state to stopped"""
    try:
        # Get current state before emergency stop
        control = bot_db.get_bot_control()
        old_state = control["actual_state"] if control else None

        # Set desired_state to 'stopped' in SQLite
        bot_db.set_bot_desired_state("stopped")
        # Also set actual_state to 'stopped' immediately
        bot_db.update_bot_actual_state("stopped", error="Emergency stop executed")
        logger.warning("Emergency stop executed via API")

        # Log emergency stop (special case of BOT_STOPPED)
        audit_trail.log(
            action=AuditAction.BOT_STOPPED,
            entity_type="bot_control",
            entity_key="bot_state",
            old_value=old_state,
            new_value="stopped",
            result="success",
            details="Emergency stop executed - immediate shutdown"
        )

        return {
            "success": True,
            "message": "Emergency Stop ausgeführt. Bot wurde sofort gestoppt."
        }
    except Exception as e:
        # Log exception to audit trail
        audit_trail.log(
            action=AuditAction.BOT_STOPPED,
            entity_type="bot_control",
            entity_key="bot_state",
            old_value=None,
            new_value="stopped",
            result="failed",
            error_message=f"Emergency stop failed: {str(e)}",
            details="Emergency stop execution error"
        )
        logger.error(f"Error in emergency stop: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

