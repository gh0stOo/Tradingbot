"""Global Events Manager - In-memory ring buffer with database persistence"""

from datetime import datetime
from typing import List, Dict, Any, Literal, Optional
from collections import deque
import logging
import sqlite3
import os

logger = logging.getLogger(__name__)

EventLevel = Literal["success", "error", "warning", "info"]

class Event:
    """Single event record"""
    def __init__(self, event_type: str, title: str, message: str, level: EventLevel = "info"):
        self.timestamp = datetime.utcnow().isoformat()
        self.type = event_type  # "bot_control", "backtest", "settings", "api_call", etc.
        self.title = title
        self.message = message
        self.level = level

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "level": self.level
        }

class EventsManager:
    """Global event ring buffer with database persistence"""
    def __init__(self, max_events: int = 100, db_path: Optional[str] = None):
        self.max_events = max_events
        self.events: deque = deque(maxlen=max_events)
        self.db_path = db_path or os.getenv("TRADING_DB_PATH", "data/trading.db")
        self._ensure_table_exists()
        logger.info(f"EventsManager initialized (max {max_events} events, persisting to {self.db_path})")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table_exists(self) -> None:
        """Create events table if it doesn't exist"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT,
                    level TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index on timestamp for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC)
            """)

            conn.commit()
            logger.debug("Events table initialized")
        except Exception as e:
            logger.error(f"Error creating events table: {e}")
        finally:
            conn.close()

    def log(self, event_type: str, title: str, message: str, level: EventLevel = "info") -> None:
        """Log a new event to memory and database"""
        event = Event(event_type, title, message, level)

        # Add to in-memory ring buffer
        self.events.append(event)

        # Persist to database
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events (timestamp, type, title, message, level)
                VALUES (?, ?, ?, ?, ?)
            """, (event.timestamp, event.type, event.title, event.message, event.level))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error persisting event to database: {e}")

        logger.debug(f"Event logged: {event_type} - {title}")

    def log_success(self, event_type: str, title: str, message: str = "") -> None:
        """Log success event"""
        self.log(event_type, title, message, "success")

    def log_error(self, event_type: str, title: str, message: str = "") -> None:
        """Log error event"""
        self.log(event_type, title, message, "error")

    def log_warning(self, event_type: str, title: str, message: str = "") -> None:
        """Log warning event"""
        self.log(event_type, title, message, "warning")

    def log_info(self, event_type: str, title: str, message: str = "") -> None:
        """Log info event"""
        self.log(event_type, title, message, "info")

    def get_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get last N events (newest first)"""
        # Convert deque to list and reverse (newest first)
        events_list = list(self.events)
        events_list.reverse()

        # Apply limit
        return [e.to_dict() for e in events_list[:limit]]

    def clear(self) -> int:
        """Clear all events, return count cleared"""
        count = len(self.events)
        self.events.clear()
        logger.info(f"Cleared {count} events")
        return count

# Global instance
_global_events_manager = EventsManager(max_events=100)

def get_events_manager() -> EventsManager:
    """Get global events manager instance"""
    return _global_events_manager
