"""WebSocket Routes for Real-time Dashboard Updates"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Any
import logging
import json

from dashboard.websocket_manager import websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time dashboard updates.
    
    Clients can connect to receive:
    - Bot status updates
    - Bot progress updates (startup, etc.)
    - Backtest progress updates
    - System notifications
    """
    client_id = None
    try:
        # Get client ID from query params if provided
        if websocket.query_params:
            client_id = websocket.query_params.get("client_id")
        
        # Connect client
        await websocket_manager.connect(websocket, client_id)
        
        # Send initial bot status
        from dashboard.bot_state_manager import BotStateManager
        state_manager = BotStateManager()
        initial_status = state_manager.get_status()
        await websocket_manager.send_personal_message({
            "type": "bot_status",
            "data": initial_status
        }, websocket)
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (ping/pong, etc.)
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                    message_type = message.get("type")
                    
                    if message_type == "ping":
                        # Respond to ping
                        await websocket_manager.send_personal_message({
                            "type": "pong",
                            "timestamp": message.get("timestamp")
                        }, websocket)
                    elif message_type == "subscribe":
                        # Client can subscribe to specific event types
                        # For now, all clients receive all updates
                        await websocket_manager.send_personal_message({
                            "type": "subscribed",
                            "events": message.get("events", ["all"])
                        }, websocket)
                    else:
                        logger.debug(f"Unknown message type from client: {message_type}")
                
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from WebSocket client: {data}")
            
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}", exc_info=True)
                break
    
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        websocket_manager.disconnect(websocket)


@router.get("/api/websocket/status")
async def get_websocket_status() -> Dict[str, Any]:
    """Get WebSocket connection status"""
    return {
        "active_connections": websocket_manager.get_connection_count(),
        "status": "operational"
    }

