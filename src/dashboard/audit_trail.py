"""Audit Trail System - Track all configuration changes and operations"""

import sqlite3
import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)

class AuditAction(str, Enum):
    """Audit action types"""
    SETTING_UPDATED = "setting_updated"
    SETTING_CREATED = "setting_created"
    SETTING_DELETED = "setting_deleted"
    EVENTS_CLEARED = "events_cleared"
    BOT_STARTED = "bot_started"
    BOT_STOPPED = "bot_stopped"
    BOT_PAUSED = "bot_paused"
    BOT_RESUMED = "bot_resumed"
    CONFIG_RELOADED = "config_reloaded"

class AuditTrail:
    """Audit trail logging system for compliance and security"""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize audit trail"""
        self.db_path = db_path or os.getenv("TRADING_DB_PATH", "data/trading.db")
        self._ensure_table_exists()
        logger.info(f"AuditTrail initialized (db: {self.db_path})")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table_exists(self) -> None:
        """Create audit_log table if it doesn't exist"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    action TEXT NOT NULL,
                    entity_type TEXT,
                    entity_key TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    user_id TEXT DEFAULT 'system',
                    ip_address TEXT,
                    result TEXT DEFAULT 'success',
                    error_message TEXT,
                    details TEXT
                )
            """)

            # Create indices for fast queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON audit_log(timestamp DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_action
                ON audit_log(action)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_entity
                ON audit_log(entity_type, entity_key)
            """)

            conn.commit()
            logger.debug("Audit log table initialized")
        except Exception as e:
            logger.error(f"Error creating audit_log table: {e}")
        finally:
            conn.close()

    def log(
        self,
        action: AuditAction,
        entity_type: Optional[str] = None,
        entity_key: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        user_id: str = "system",
        ip_address: Optional[str] = None,
        result: str = "success",
        error_message: Optional[str] = None,
        details: Optional[str] = None
    ) -> bool:
        """Log an audit trail entry"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO audit_log
                (action, entity_type, entity_key, old_value, new_value,
                 user_id, ip_address, result, error_message, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                action.value,
                entity_type,
                entity_key,
                old_value,
                new_value,
                user_id,
                ip_address,
                result,
                error_message,
                details
            ))

            conn.commit()
            conn.close()

            logger.info(f"Audit: {action.value} on {entity_key} by {user_id} - {result}")
            return True
        except Exception as e:
            logger.error(f"Error logging audit trail: {e}")
            return False

    def get_audit_log(
        self,
        action: Optional[str] = None,
        entity_key: Optional[str] = None,
        user_id: Optional[str] = None,
        days: int = 30,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Get audit log entries with optional filtering"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Build WHERE clause
            where_clauses = [f"timestamp >= datetime('now', '-{days} days')"]
            params = []

            if action:
                where_clauses.append("action = ?")
                params.append(action)

            if entity_key:
                where_clauses.append("entity_key = ?")
                params.append(entity_key)

            if user_id:
                where_clauses.append("user_id = ?")
                params.append(user_id)

            where_clause = " AND ".join(where_clauses)

            cursor.execute(f"""
                SELECT * FROM audit_log
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
            """, params + [limit])

            rows = cursor.fetchall()
            conn.close()

            entries = [dict(row) for row in rows]

            return {
                "success": True,
                "entries": entries,
                "count": len(entries)
            }
        except Exception as e:
            logger.error(f"Error retrieving audit log: {e}")
            return {
                "success": False,
                "error": str(e),
                "entries": []
            }

    def get_change_history(self, entity_key: str) -> Dict[str, Any]:
        """Get all changes to a specific entity"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT timestamp, action, old_value, new_value, user_id, result
                FROM audit_log
                WHERE entity_key = ?
                ORDER BY timestamp ASC
            """, (entity_key,))

            rows = cursor.fetchall()
            conn.close()

            history = [dict(row) for row in rows]

            return {
                "success": True,
                "entity_key": entity_key,
                "history": history,
                "total_changes": len(history)
            }
        except Exception as e:
            logger.error(f"Error retrieving change history: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_user_activity(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get all activities by a specific user"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    action,
                    COUNT(*) as count,
                    SUM(CASE WHEN result = 'success' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN result = 'failed' THEN 1 ELSE 0 END) as failed
                FROM audit_log
                WHERE user_id = ? AND timestamp >= datetime('now', '-' || ? || ' days')
                GROUP BY action
                ORDER BY count DESC
            """, (user_id, days))

            stats = [dict(row) for row in cursor.fetchall()]

            # Get recent entries
            cursor.execute("""
                SELECT timestamp, action, entity_key, result
                FROM audit_log
                WHERE user_id = ? AND timestamp >= datetime('now', '-' || ? || ' days')
                ORDER BY timestamp DESC
                LIMIT 50
            """, (user_id, days))

            recent = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return {
                "success": True,
                "user_id": user_id,
                "period_days": days,
                "action_summary": stats,
                "recent_activities": recent
            }
        except Exception as e:
            logger.error(f"Error retrieving user activity: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_failed_operations(self, days: int = 7) -> Dict[str, Any]:
        """Get all failed operations (for forensics)"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT timestamp, action, entity_key, user_id, error_message
                FROM audit_log
                WHERE result = 'failed' AND timestamp >= datetime('now', '-' || ? || ' days')
                ORDER BY timestamp DESC
            """, (days,))

            failures = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return {
                "success": True,
                "period_days": days,
                "failures": failures,
                "failure_count": len(failures)
            }
        except Exception as e:
            logger.error(f"Error retrieving failed operations: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Global instance
_global_audit_trail: Optional[AuditTrail] = None

def get_audit_trail() -> AuditTrail:
    """Get or create global audit trail instance"""
    global _global_audit_trail
    if _global_audit_trail is None:
        _global_audit_trail = AuditTrail()
    return _global_audit_trail
