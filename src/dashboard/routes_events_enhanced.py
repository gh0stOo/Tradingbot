"""Enhanced Events API Routes - Advanced filtering, search, and statistics"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import sqlite3
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter()

DB_PATH = os.getenv("TRADING_DB_PATH", "data/trading.db")

def _get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============ GET /api/events ============

@router.get("/api/events")
async def get_events(limit: int = Query(50, ge=1, le=1000)) -> Dict[str, Any]:
    """Get most recent events from ring buffer"""
    from dashboard.events_manager import get_events_manager

    try:
        events_manager = get_events_manager()
        events = events_manager.get_events(limit=limit)

        return {
            "success": True,
            "events": events,
            "count": len(events),
            "total_capacity": events_manager.max_events,
            "source": "memory"  # Ring buffer
        }
    except Exception as e:
        logger.error(f"Error getting events: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# ============ GET /api/events/filter - ADVANCED FILTERING ============

@router.get("/api/events/filter")
async def filter_events(
    event_type: Optional[str] = Query(None, description="Filter by event type (bot_control, backtest, settings)"),
    level: Optional[str] = Query(None, description="Filter by level (success, error, warning, info)"),
    start_date: Optional[str] = Query(None, description="ISO 8601 start date"),
    end_date: Optional[str] = Query(None, description="ISO 8601 end date"),
    limit: int = Query(50, ge=1, le=1000)
) -> Dict[str, Any]:
    """Filter events by type, level, and date range from persistent database"""
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        # Build WHERE clause
        where_clauses = []
        params = []

        if event_type:
            where_clauses.append("type = ?")
            params.append(event_type)

        if level:
            where_clauses.append("level = ?")
            params.append(level)

        if start_date:
            where_clauses.append("timestamp >= ?")
            params.append(start_date)

        if end_date:
            where_clauses.append("timestamp <= ?")
            params.append(end_date)

        where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Query database
        query = f"""
            SELECT timestamp, type, title, message, level
            FROM events
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        events = [dict(row) for row in rows]

        return {
            "success": True,
            "events": events,
            "count": len(events),
            "filters": {
                "event_type": event_type,
                "level": level,
                "start_date": start_date,
                "end_date": end_date
            },
            "source": "database"
        }
    except Exception as e:
        logger.error(f"Error filtering events: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# ============ GET /api/events/search - FULL-TEXT SEARCH ============

@router.get("/api/events/search")
async def search_events(
    query: str = Query(..., min_length=1, max_length=255, description="Search term for title/message"),
    limit: int = Query(50, ge=1, le=1000)
) -> Dict[str, Any]:
    """Full-text search events by title and message"""
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        # Use LIKE for case-insensitive search
        search_term = f"%{query}%"

        cursor.execute("""
            SELECT timestamp, type, title, message, level
            FROM events
            WHERE title LIKE ? OR message LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (search_term, search_term, limit))

        rows = cursor.fetchall()
        conn.close()

        events = [dict(row) for row in rows]

        return {
            "success": True,
            "events": events,
            "count": len(events),
            "search_query": query,
            "source": "database"
        }
    except Exception as e:
        logger.error(f"Error searching events: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# ============ GET /api/events/stats - EVENT STATISTICS ============

@router.get("/api/events/stats")
async def get_event_stats(
    days: int = Query(7, ge=1, le=365, description="Days of history to analyze")
) -> Dict[str, Any]:
    """Get event statistics: counts by type and level, timeline"""
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()

        # Calculate start date
        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Count by type
        cursor.execute("""
            SELECT type, COUNT(*) as count
            FROM events
            WHERE timestamp >= ?
            GROUP BY type
            ORDER BY count DESC
        """, (start_date,))
        count_by_type = {row[0]: row[1] for row in cursor.fetchall()}

        # Count by level
        cursor.execute("""
            SELECT level, COUNT(*) as count
            FROM events
            WHERE timestamp >= ?
            GROUP BY level
            ORDER BY count DESC
        """, (start_date,))
        count_by_level = {row[0]: row[1] for row in cursor.fetchall()}

        # Events per hour (timeline)
        cursor.execute("""
            SELECT strftime('%Y-%m-%d %H:00:00', timestamp) as hour, COUNT(*) as count
            FROM events
            WHERE timestamp >= ?
            GROUP BY hour
            ORDER BY hour DESC
            LIMIT 24
        """, (start_date,))
        timeline = [{"hour": row[0], "count": row[1]} for row in cursor.fetchall()]

        # Total events
        cursor.execute("""
            SELECT COUNT(*) FROM events WHERE timestamp >= ?
        """, (start_date,))
        total_events = cursor.fetchone()[0]

        conn.close()

        return {
            "success": True,
            "stats": {
                "total_events": total_events,
                "count_by_type": count_by_type,
                "count_by_level": count_by_level,
                "timeline": list(reversed(timeline))  # Chronological order
            },
            "period_days": days,
            "source": "database"
        }
    except Exception as e:
        logger.error(f"Error getting event stats: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# ============ POST /api/events/clear ============

@router.post("/api/events/clear")
async def clear_events() -> Dict[str, Any]:
    """Clear all events from ring buffer and optionally archive to database"""
    try:
        from dashboard.events_manager import get_events_manager

        events_manager = get_events_manager()
        cleared_count = events_manager.clear()

        return {
            "success": True,
            "message": f"Cleared {cleared_count} events from memory",
            "cleared_count": cleared_count,
            "note": "Database events are retained for historical queries"
        }
    except Exception as e:
        logger.error(f"Error clearing events: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )
