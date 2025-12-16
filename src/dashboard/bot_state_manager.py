"""Bot State Manager - Manages bot state across the application"""

import threading
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class BotStatus(Enum):
    """Bot status enumeration"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class BotStateManager:
    """
    Manages bot state for dashboard and API access.
    Thread-safe singleton pattern.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(BotStateManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._state_lock = threading.Lock()
        
        # Bot state
        self.status: BotStatus = BotStatus.STOPPED
        self.mode: str = "PAPER"  # PAPER, TESTNET, LIVE
        self.start_time: Optional[datetime] = None
        self.last_execution: Optional[datetime] = None
        self.error_message: Optional[str] = None
        
        # Callbacks for state changes
        self._status_callbacks: list[Callable[[BotStatus], None]] = []
        
        # Bot process reference (will be set by main.py)
        self._bot_process: Optional[Any] = None
        self._bot_thread: Optional[threading.Thread] = None
        
        # Progress tracking for startup
        self._startup_progress: int = 0
        self._startup_message: Optional[str] = None
        self._startup_status: Optional[str] = None  # "initializing", "starting", "running", "error"
        
        logger.info("BotStateManager initialized")
    
    def register_callback(self, callback: Callable[[BotStatus], None]) -> None:
        """Register a callback for status changes"""
        with self._state_lock:
            self._status_callbacks.append(callback)
    
    def _notify_callbacks(self, new_status: BotStatus) -> None:
        """Notify all registered callbacks of status change"""
        for callback in self._status_callbacks:
            try:
                callback(new_status)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")
    
    def set_bot_reference(self, bot_process: Any, bot_thread: Optional[threading.Thread] = None) -> None:
        """Set reference to bot process/thread"""
        with self._state_lock:
            self._bot_process = bot_process
            self._bot_thread = bot_thread
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        with self._state_lock:
            uptime_seconds = 0
            if self.start_time:
                uptime_seconds = int((datetime.utcnow() - self.start_time).total_seconds())
            
            status_data = {
                "status": self.status.value,
                "mode": self.mode,
                "uptime": self._format_uptime(uptime_seconds),
                "lastExecution": self.last_execution.isoformat() if self.last_execution else None,
                "startTime": self.start_time.isoformat() if self.start_time else None,
                "error": self.error_message
            }
            
            # Add startup progress if available
            if self._startup_progress > 0:
                status_data["startupProgress"] = {
                    "progress": self._startup_progress,
                    "message": self._startup_message,
                    "status": self._startup_status
                }
            
            return status_data
    
    def set_status(self, status: BotStatus, error_message: Optional[str] = None) -> None:
        """Set bot status"""
        with self._state_lock:
            old_status = self.status
            self.status = status
            self.error_message = error_message
            
            if status == BotStatus.RUNNING and not self.start_time:
                self.start_time = datetime.utcnow()
            elif status == BotStatus.STOPPED:
                self.start_time = None
                self._startup_progress = 0
                self._startup_message = None
                self._startup_status = None
            
            if old_status != status:
                logger.info(f"Bot status changed: {old_status.value} -> {status.value}")
                self._notify_callbacks(status)
                # Broadcast status update via WebSocket
                self._broadcast_status_update()
    
    def set_startup_progress(self, progress: int, message: Optional[str] = None, status: Optional[str] = None) -> None:
        """Set startup progress (0-100)"""
        with self._state_lock:
            self._startup_progress = max(0, min(100, progress))
            if message:
                self._startup_message = message
            if status:
                self._startup_status = status
            # Broadcast progress update via WebSocket
            self._broadcast_progress_update()
    
    def get_startup_progress(self) -> Dict[str, Any]:
        """Get current startup progress"""
        with self._state_lock:
            return {
                "progress": self._startup_progress,
                "message": self._startup_message,
                "status": self._startup_status
            }
    
    def _broadcast_status_update(self) -> None:
        """Broadcast status update via WebSocket (async)"""
        try:
            # Import here to avoid circular dependency
            from dashboard.websocket_manager import websocket_manager
            import asyncio
            
            # Get current status
            status_data = self.get_status()
            
            # Try to send update (non-blocking)
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, schedule coroutine
                    asyncio.create_task(websocket_manager.send_bot_status_update(status_data))
                else:
                    # If no loop running, run coroutine
                    asyncio.run(websocket_manager.send_bot_status_update(status_data))
            except RuntimeError:
                # No event loop, create new one
                asyncio.run(websocket_manager.send_bot_status_update(status_data))
        except Exception as e:
            # Don't fail if WebSocket is not available
            logger.debug(f"Could not broadcast status update via WebSocket: {e}")
    
    def _broadcast_progress_update(self) -> None:
        """Broadcast progress update via WebSocket (async)"""
        try:
            from dashboard.websocket_manager import websocket_manager
            import asyncio
            
            progress_data = self.get_startup_progress()
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(websocket_manager.send_bot_progress_update(
                        progress_data["progress"],
                        progress_data["message"],
                        progress_data["status"]
                    ))
                else:
                    asyncio.run(websocket_manager.send_bot_progress_update(
                        progress_data["progress"],
                        progress_data["message"],
                        progress_data["status"]
                    ))
            except RuntimeError:
                asyncio.run(websocket_manager.send_bot_progress_update(
                    progress_data["progress"],
                    progress_data["message"],
                    progress_data["status"]
                ))
        except Exception as e:
            logger.debug(f"Could not broadcast progress update via WebSocket: {e}")
    
    def update_last_execution(self) -> None:
        """Update last execution timestamp"""
        with self._state_lock:
            self.last_execution = datetime.utcnow()
    
    def set_mode(self, mode: str) -> None:
        """Set trading mode"""
        with self._state_lock:
            self.mode = mode
            logger.info(f"Bot mode set to: {mode}")
    
    def start_bot(self) -> bool:
        """Start the bot (returns True if successful)"""
        with self._state_lock:
            if self.status == BotStatus.RUNNING:
                logger.warning("Bot is already running")
                return False
            
            # This will be handled by main.py
            # For now, we just set the status
            self.set_status(BotStatus.RUNNING)
            return True
    
    def stop_bot(self) -> bool:
        """Stop the bot (returns True if successful)"""
        with self._state_lock:
            if self.status == BotStatus.STOPPED:
                logger.warning("Bot is already stopped")
                return False
            
            self.set_status(BotStatus.STOPPED)
            return True
    
    def pause_bot(self) -> bool:
        """Pause the bot (returns True if successful)"""
        with self._state_lock:
            if self.status != BotStatus.RUNNING:
                logger.warning("Bot must be running to pause")
                return False
            
            self.set_status(BotStatus.PAUSED)
            return True
    
    def resume_bot(self) -> bool:
        """Resume the bot (returns True if successful)"""
        with self._state_lock:
            if self.status != BotStatus.PAUSED:
                logger.warning("Bot must be paused to resume")
                return False
            
            self.set_status(BotStatus.RUNNING)
            self.update_last_execution()
            return True
    
    def emergency_stop(self) -> bool:
        """Emergency stop - immediately stop bot"""
        with self._state_lock:
            logger.warning("Emergency stop executed")
            self.set_status(BotStatus.STOPPED)
            # Close all positions will be handled via TradingState
            # This is triggered through the API route which has access to TradingState
            return True
    
    def get_trading_state_reference(self) -> Optional[Any]:
        """Get reference to TradingState (set by main.py)"""
        with self._state_lock:
            return getattr(self, '_trading_state', None)
    
    def set_trading_state_reference(self, trading_state: Any) -> None:
        """Set reference to TradingState"""
        with self._state_lock:
            self._trading_state = trading_state
    
    def _format_uptime(self, seconds: int) -> str:
        """Format uptime in seconds to human readable string"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"

