"""Settings Persistence Layer - SQLite-based storage for user-configurable settings"""

import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Optional, Dict
import os

logger = logging.getLogger(__name__)

class SettingsDatabase:
    """Manages persistent storage of settings in SQLite database"""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize settings database connection"""
        if db_path is None:
            db_path = os.getenv("TRADING_DB_PATH", "data/trading.db")

        self.db_path = db_path
        self._ensure_table_exists()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table_exists(self) -> None:
        """Create settings table if it doesn't exist"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    value_type TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_by TEXT DEFAULT 'system'
                )
            """)

            conn.commit()
            logger.debug("Settings table initialized")
        except Exception as e:
            logger.error(f"Error creating settings table: {e}")
        finally:
            conn.close()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value from database"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT value, value_type FROM settings WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                return self._deserialize_value(row[0], row[1])
            return default
        except Exception as e:
            logger.error(f"Error getting setting {key}: {e}")
            return default

    def set(self, key: str, value: Any, value_type: Optional[str] = None, updated_by: str = "api") -> bool:
        """Set a setting value in database"""
        try:
            if value_type is None:
                value_type = self._infer_type(value)

            serialized = self._serialize_value(value, value_type)

            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO settings (key, value, value_type, updated_at, updated_by)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, (key, serialized, value_type, updated_by))

            conn.commit()
            conn.close()

            logger.info(f"Setting {key} updated to {value} by {updated_by}")
            return True
        except Exception as e:
            logger.error(f"Error setting {key}: {e}")
            return False

    def get_all(self) -> Dict[str, Any]:
        """Get all settings from database"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT key, value, value_type FROM settings")
            rows = cursor.fetchall()
            conn.close()

            settings = {}
            for row in rows:
                key = row[0]
                value = self._deserialize_value(row[1], row[2])
                settings[key] = value

            return settings
        except Exception as e:
            logger.error(f"Error getting all settings: {e}")
            return {}

    def delete(self, key: str) -> bool:
        """Delete a setting from database"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM settings WHERE key = ?", (key,))

            conn.commit()
            conn.close()

            logger.info(f"Setting {key} deleted")
            return True
        except Exception as e:
            logger.error(f"Error deleting {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if setting exists in database"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT 1 FROM settings WHERE key = ? LIMIT 1", (key,))
            exists = cursor.fetchone() is not None
            conn.close()

            return exists
        except Exception as e:
            logger.error(f"Error checking if {key} exists: {e}")
            return False

    def clear_all(self) -> bool:
        """Clear all settings from database"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM settings")

            conn.commit()
            conn.close()

            logger.warning("All settings cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing all settings: {e}")
            return False

    @staticmethod
    def _serialize_value(value: Any, value_type: str) -> str:
        """Serialize value for storage in database"""
        if value_type == "json":
            return json.dumps(value)
        elif value_type in ("integer", "number"):
            return str(value)
        elif value_type == "boolean":
            return "1" if value else "0"
        else:
            return str(value)

    @staticmethod
    def _deserialize_value(serialized: str, value_type: str) -> Any:
        """Deserialize value from database storage"""
        try:
            if value_type == "json":
                return json.loads(serialized)
            elif value_type == "integer":
                return int(serialized)
            elif value_type == "number":
                return float(serialized)
            elif value_type == "boolean":
                return serialized == "1"
            else:
                return serialized
        except Exception as e:
            logger.error(f"Error deserializing {serialized} as {value_type}: {e}")
            return serialized

    @staticmethod
    def _infer_type(value: Any) -> str:
        """Infer type of value"""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, (list, dict)):
            return "json"
        else:
            return "string"


# Global instance
_global_settings_db: Optional[SettingsDatabase] = None

def get_settings_db() -> SettingsDatabase:
    """Get or create global settings database instance"""
    global _global_settings_db
    if _global_settings_db is None:
        _global_settings_db = SettingsDatabase()
    return _global_settings_db
