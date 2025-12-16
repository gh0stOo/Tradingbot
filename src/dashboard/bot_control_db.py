"""Bot Control Database - SQLite-based state management for Docker compatibility"""

import logging
from typing import Optional, Dict, Any
from data.database import Database

logger = logging.getLogger(__name__)


class BotControlDB:
    """
    SQLite-based bot control for Docker compatibility.
    Worker reads desired_state and writes actual_state + heartbeat.
    """
    
    def __init__(self, db_path: str = "data/trading.db"):
        """
        Initialize BotControlDB
        
        Args:
            db_path: Path to SQLite database
        """
        self.db = Database(db_path)
        logger.info(f"BotControlDB initialized with database: {db_path}")
    
    def get_desired_state(self) -> Optional[str]:
        """
        Get desired bot state from SQLite
        
        Returns:
            'stopped', 'running', 'paused', or None if not found
        """
        control = self.db.get_bot_control()
        return control.get("desired_state") if control else None
    
    def get_actual_state(self) -> Optional[str]:
        """
        Get actual bot state from SQLite
        
        Returns:
            'stopped', 'running', 'paused', 'error', or None if not found
        """
        control = self.db.get_bot_control()
        return control.get("actual_state") if control else None
    
    def get_control_state(self) -> Optional[Dict[str, Any]]:
        """
        Get full bot control state from SQLite
        
        Returns:
            Dictionary with all bot_control fields or None
        """
        return self.db.get_bot_control()
    
    def update_actual_state(self, state: str, error: Optional[str] = None) -> None:
        """
        Update actual bot state in SQLite
        
        Args:
            state: 'stopped', 'running', 'paused', or 'error'
            error: Optional error message
        """
        self.db.update_bot_actual_state(state, error)
        logger.debug(f"Updated actual_state to {state}")
    
    def update_heartbeat(self) -> None:
        """Update bot heartbeat timestamp in SQLite"""
        self.db.update_bot_heartbeat()
    
    def set_desired_state(self, state: str) -> None:
        """
        Set desired bot state in SQLite (usually called by API)
        
        Args:
            state: 'stopped', 'running', or 'paused'
        """
        self.db.set_bot_desired_state(state)
        logger.debug(f"Set desired_state to {state}")

    def close(self) -> None:
        """Close underlying database connection."""
        try:
            self.db.close()
        except Exception:
            pass

    def __del__(self):
        self.close()
