"""Bybit WebSocket Client for Real-time Order and Position Updates"""

import json
import logging
import threading
import time
import hmac
import hashlib
from typing import Dict, Optional, Callable, Any
from datetime import datetime
import websocket
from decimal import Decimal

logger = logging.getLogger(__name__)


class BybitWebSocketClient:
    """
    WebSocket client for Bybit private channel subscriptions.
    
    Handles:
    - Order execution updates
    - Position updates
    - Reconnection logic
    - Authentication
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        on_order_update: Optional[Callable[[Dict], None]] = None,
        on_position_update: Optional[Callable[[Dict], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ):
        """
        Initialize Bybit WebSocket client.
        
        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
            testnet: Use testnet (default: False)
            on_order_update: Callback for order updates
            on_position_update: Callback for position updates
            on_error: Callback for errors
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # WebSocket URLs
        if testnet:
            self.ws_url = "wss://stream-testnet.bybit.com/v5/private"
        else:
            self.ws_url = "wss://stream.bybit.com/v5/private"
        
        # Callbacks
        self.on_order_update = on_order_update
        self.on_position_update = on_position_update
        self.on_error = on_error
        
        # Connection state
        self.ws: Optional[websocket.WebSocketApp] = None
        self.connected = False
        self.authenticated = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5  # seconds
        
        # Threading
        self.ws_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Heartbeat
        self.last_pong = time.time()
        self.heartbeat_interval = 20  # seconds
        self.heartbeat_thread: Optional[threading.Thread] = None
        
        logger.info(f"BybitWebSocketClient initialized (testnet={testnet})")
    
    def _generate_auth_message(self) -> Dict[str, Any]:
        """Generate authentication message for WebSocket"""
        expires = int((time.time() + 10000) * 1000)  # 10 seconds from now
        
        # Create signature
        signature_string = f"GET/realtime{expires}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "op": "auth",
            "args": [self.api_key, expires, signature]
        }
    
    def _on_message(self, ws: websocket.WebSocketApp, message: str) -> None:
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            
            # Handle authentication response
            if "op" in data and data["op"] == "auth":
                if data.get("success"):
                    self.authenticated = True
                    logger.info("WebSocket authenticated successfully")
                    self._subscribe_to_channels()
                else:
                    logger.error(f"WebSocket authentication failed: {data.get('ret_msg', 'Unknown error')}")
                    self.on_error(Exception(f"Authentication failed: {data.get('ret_msg')}"))
                return
            
            # Handle subscription response
            if "op" in data and data["op"] == "subscribe":
                if data.get("success"):
                    logger.info(f"Subscribed to: {data.get('req_id', 'unknown')}")
                else:
                    logger.error(f"Subscription failed: {data.get('ret_msg', 'Unknown error')}")
                return
            
            # Handle pong (heartbeat response)
            if "op" in data and data["op"] == "pong":
                self.last_pong = time.time()
                return
            
            # Handle topic data
            if "topic" in data:
                topic = data["topic"]
                topic_data = data.get("data", [])
                
                # Validate topic_data is a list
                if not isinstance(topic_data, list):
                    logger.warning(f"Invalid topic data format (expected list): {topic_data}")
                    return
                
                if "order" in topic:
                    # Order execution update
                    for order_data in topic_data:
                        # Validate order_data structure
                        if not isinstance(order_data, dict):
                            logger.warning(f"Invalid order data format (expected dict): {order_data}")
                            continue
                        if self.on_order_update:
                            self.on_order_update(order_data)
                
                elif "position" in topic:
                    # Position update
                    for position_data in topic_data:
                        # Validate position_data structure
                        if not isinstance(position_data, dict):
                            logger.warning(f"Invalid position data format (expected dict): {position_data}")
                            continue
                        if not position_data.get("symbol"):
                            logger.warning(f"Position data missing symbol: {position_data}")
                            continue
                        if self.on_position_update:
                            self.on_position_update(position_data)
                
                elif "execution" in topic:
                    # Trade execution (fill)
                    for execution_data in topic_data:
                        # Validate execution_data structure
                        if not isinstance(execution_data, dict):
                            logger.warning(f"Invalid execution data format (expected dict): {execution_data}")
                            continue
                        if self.on_order_update:
                            self.on_order_update(execution_data)
        
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}", exc_info=True)
            if self.on_error:
                self.on_error(e)
    
    def _on_error(self, ws: websocket.WebSocketApp, error: Exception) -> None:
        """Handle WebSocket errors"""
        logger.error(f"WebSocket error: {error}", exc_info=True)
        self.connected = False
        self.authenticated = False
        
        if self.on_error:
            self.on_error(error)
    
    def _on_close(self, ws: websocket.WebSocketApp, close_status_code: int, close_msg: str) -> None:
        """Handle WebSocket close"""
        logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.connected = False
        self.authenticated = False
        
        # Attempt reconnection if running
        if self.running:
            self._reconnect()
    
    def _on_open(self, ws: websocket.WebSocketApp) -> None:
        """Handle WebSocket open"""
        logger.info("WebSocket connection opened")
        self.connected = True
        self.reconnect_attempts = 0
        
        # Authenticate
        auth_msg = self._generate_auth_message()
        ws.send(json.dumps(auth_msg))
    
    def _subscribe_to_channels(self) -> None:
        """Subscribe to order and position update channels"""
        if not self.ws or not self.authenticated:
            return
        
        subscriptions = {
            "op": "subscribe",
            "args": [
                "order",  # Order updates
                "execution",  # Trade executions (fills)
                "position"  # Position updates
            ]
        }
        
        self.ws.send(json.dumps(subscriptions))
        logger.info("Subscribed to order, execution, and position channels")
    
    def _send_heartbeat(self) -> None:
        """Send heartbeat (ping) to keep connection alive"""
        while self.running and self.connected:
            try:
                if self.ws and self.connected:
                    ping_msg = {"op": "ping"}
                    self.ws.send(json.dumps(ping_msg))
                    
                    # Check if we received pong
                    if time.time() - self.last_pong > self.heartbeat_interval * 2:
                        logger.warning("No pong received, connection may be dead")
                        self.connected = False
                
                time.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}", exc_info=True)
                time.sleep(self.heartbeat_interval)
    
    def _reconnect(self) -> None:
        """Attempt to reconnect WebSocket"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error("Max reconnect attempts reached, stopping")
            self.running = False
            return
        
        self.reconnect_attempts += 1
        wait_time = self.reconnect_delay * self.reconnect_attempts
        
        logger.info(f"Attempting to reconnect in {wait_time} seconds (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        time.sleep(wait_time)
        
        if self.running:
            self.connect()
    
    def connect(self) -> None:
        """Connect to WebSocket"""
        if self.ws and self.connected:
            logger.warning("WebSocket already connected")
            return
        
        try:
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # Start WebSocket in separate thread
            self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
            self.ws_thread.start()
            
            # Start heartbeat thread
            if not self.heartbeat_thread or not self.heartbeat_thread.is_alive():
                self.heartbeat_thread = threading.Thread(target=self._send_heartbeat, daemon=True)
                self.heartbeat_thread.start()
            
            logger.info("WebSocket connection initiated")
        
        except Exception as e:
            logger.error(f"Error connecting WebSocket: {e}", exc_info=True)
            if self.on_error:
                self.on_error(e)
    
    def disconnect(self) -> None:
        """Disconnect from WebSocket"""
        self.running = False
        
        if self.ws:
            self.ws.close()
        
        self.connected = False
        self.authenticated = False
        logger.info("WebSocket disconnected")
    
    def start(self) -> None:
        """Start WebSocket client"""
        if self.running:
            logger.warning("WebSocket client already running")
            return
        
        self.running = True
        self.connect()
        logger.info("WebSocket client started")
    
    def stop(self) -> None:
        """Stop WebSocket client"""
        self.running = False
        self.disconnect()
        logger.info("WebSocket client stopped")
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected and authenticated"""
        return self.connected and self.authenticated

