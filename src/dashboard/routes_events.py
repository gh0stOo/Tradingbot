"""Events API Routes - Operational event logging and retrieval"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from typing import Dict, Any
import logging

from dashboard.events_manager import get_events_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# ============ GET EVENTS ENDPOINT ============

@router.get("/api/events")
async def get_events(limit: int = 50) -> Dict[str, Any]:
    """Get operational events from ring buffer (newest first)"""
    try:
        events_manager = get_events_manager()
        events = events_manager.get_events(limit=limit)

        return {
            "success": True,
            "events": events,
            "count": len(events),
            "total_capacity": events_manager.max_events
        }
    except Exception as e:
        logger.error(f"Error getting events: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# ============ CLEAR EVENTS ENDPOINT ============

@router.post("/api/events/clear")
async def clear_events() -> Dict[str, Any]:
    """Clear all events from ring buffer"""
    try:
        events_manager = get_events_manager()
        cleared_count = events_manager.clear()

        return {
            "success": True,
            "message": f"Cleared {cleared_count} events",
            "cleared_count": cleared_count
        }
    except Exception as e:
        logger.error(f"Error clearing events: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )
