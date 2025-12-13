"""Bot-API Integration Helper"""

import requests
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class BotAPIClient:
    """Client to send signals to API server for n8n"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        """
        Initialize API client
        
        Args:
            api_base_url: Base URL of the API server
        """
        self.base_url = api_base_url.rstrip('/')
    
    def send_signal(self, trade_result: Dict[str, Any]) -> bool:
        """
        Send trade signal to API endpoint
        
        Args:
            trade_result: Trade result dictionary from bot
            
        Returns:
            True if successful, False otherwise
        """
        try:
            signal = trade_result.get("signal", {})
            execution = trade_result.get("execution", {})
            position = trade_result.get("position", {})
            
            signal_data = {
                "symbol": trade_result.get("symbol"),
                "side": signal.get("side"),
                "price": trade_result.get("price"),
                "confidence": signal.get("confidence"),
                "strategies": signal.get("strategiesUsed", []),
                "regime": trade_result.get("regime", {}).get("type", "unknown"),
                "orderId": execution.get("orderId"),
                "qty": position.get("qty"),
                "stopLoss": position.get("stopLoss"),
                "takeProfit": position.get("takeProfit")
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/trade/signal",
                json=signal_data,
                timeout=5
            )
            response.raise_for_status()
            logger.info(f"Signal sent to API for {signal_data['symbol']}")
            return True
        except Exception as e:
            logger.error(f"Failed to send signal to API: {e}")
            return False

