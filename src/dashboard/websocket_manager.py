"""WebSocket Manager for Real-time Dashboard Updates"""

import json
import asyncio
import logging
from typing import Set, Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections for real-time dashboard updates.
    Thread-safe singleton pattern.
    """
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WebSocketManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        # Active WebSocket connections
        self.active_connections: Set[WebSocket] = set()
        # Connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        
        logger.info("WebSocketManager initialized")
    
    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None) -> None:
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        
        metadata = {
            "client_id": client_id or f"client_{id(websocket)}",
            "connected_at": datetime.utcnow().isoformat(),
            "last_ping": datetime.utcnow().isoformat()
        }
        self.connection_metadata[websocket] = metadata
        
        logger.info(f"WebSocket client connected: {metadata['client_id']}")
        
        # Send initial status
        await self.send_personal_message({
            "type": "connection",
            "status": "connected",
            "client_id": metadata["client_id"],
            "timestamp": datetime.utcnow().isoformat()
        }, websocket)
    
    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            metadata = self.connection_metadata.get(websocket, {})
            client_id = metadata.get("client_id", "unknown")
            
            self.active_connections.remove(websocket)
            if websocket in self.connection_metadata:
                del self.connection_metadata[websocket]
            
            logger.info(f"WebSocket client disconnected: {client_id}")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket) -> None:
        """Send a message to a specific WebSocket connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcast a message to all connected WebSocket clients"""
        if not self.active_connections:
            return
        
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.utcnow().isoformat()
        
        disconnected = set()
        for connection in self.active_connections.copy():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Error broadcasting to WebSocket: {e}")
                disconnected.add(connection)
        
        # Remove disconnected connections
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_bot_status_update(self, status_data: Dict[str, Any]) -> None:
        """Send bot status update to all connected clients"""
        await self.broadcast({
            "type": "bot_status",
            "data": status_data
        })
    
    async def send_bot_progress_update(self, progress: int, message: Optional[str] = None, status: Optional[str] = None) -> None:
        """Send bot progress update (for startup, etc.)"""
        await self.broadcast({
            "type": "bot_progress",
            "progress": progress,
            "message": message,
            "status": status
        })
    
    async def send_backtest_update(self, backtest_id: str, update_data: Dict[str, Any]) -> None:
        """Send backtest update to all connected clients"""
        await self.broadcast({
            "type": "backtest_update",
            "backtest_id": backtest_id,
            "data": update_data
        })
    
    def get_connection_count(self) -> int:
        """Get number of active WebSocket connections"""
        return len(self.active_connections)
    
    async def ping_all(self) -> None:
        """Send ping to all connections to keep them alive"""
        await self.broadcast({
            "type": "ping",
            "timestamp": datetime.utcnow().isoformat()
        })


# Global instance
websocket_manager = WebSocketManager()

