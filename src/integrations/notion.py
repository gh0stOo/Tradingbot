"""Notion Integration"""

from typing import Dict, Any, Optional
from notion_client import Client
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class NotionIntegration:
    """Notion API Integration"""
    
    def __init__(self, api_key: str, database_ids: Dict[str, str]):
        """
        Initialize Notion integration
        
        Args:
            api_key: Notion API key
            database_ids: Dictionary with database IDs (signals, executions, dailyStats)
        """
        self.client = Client(auth=api_key)
        self.databases = database_ids
    
    def log_signal(self, signal_data: Dict[str, Any]) -> Optional[str]:
        """
        Log trading signal to Notion
        
        Args:
            signal_data: Signal data dictionary
            
        Returns:
            Page ID if successful, None otherwise
        """
        try:
            signal = signal_data.get("signal", {})
            symbol = signal_data.get("symbol", "")
            price = signal_data.get("price", 0)
            regime = signal_data.get("regime", {})
            
            properties = {
                "Symbol": {
                    "title": [{"text": {"content": symbol}}]
                },
                "Side": {
                    "select": {"name": signal.get("side", "Hold")}
                },
                "Confidence": {
                    "number": round(signal.get("confidence", 0), 4)
                },
                "Quality Score": {
                    "number": round(signal.get("qualityScore", 0), 4)
                },
                "Price": {
                    "number": round(price, 4)
                },
                "Strategies": {
                    "multi_select": [
                        {"name": s} for s in signal.get("strategiesUsed", [])
                    ]
                },
                "Regime": {
                    "select": {"name": regime.get("type", "unknown")}
                },
                "Timestamp": {
                    "date": {"start": datetime.utcnow().isoformat()}
                }
            }
            
            page = self.client.pages.create(
                parent={"database_id": self.databases.get("signals", "")},
                properties=properties
            )
            
            return page.get("id")
        except Exception as e:
            logger.error(f"Error logging signal to Notion: {e}", exc_info=True)
            return None
    
    def log_execution(self, execution_data: Dict[str, Any]) -> Optional[str]:
        """
        Log execution to Notion
        
        Args:
            execution_data: Execution data dictionary
            
        Returns:
            Page ID if successful, None otherwise
        """
        try:
            execution = execution_data.get("execution", {})
            symbol = execution_data.get("symbol", "")
            signal = execution_data.get("signal", {})
            position = execution_data.get("position", {})
            
            properties = {
                "Symbol": {
                    "title": [{"text": {"content": symbol}}]
                },
                "Side": {
                    "select": {"name": signal.get("side", "Hold")}
                },
                "Order ID": {
                    "rich_text": [{"text": {"content": execution.get("orderId", "N/A")}}]
                },
                "Quantity": {
                    "number": position.get("qty", 0)
                },
                "Price": {
                    "number": round(execution.get("price", 0), 4)
                },
                "Stop Loss": {
                    "number": round(position.get("stopLoss", 0), 4)
                },
                "Take Profit": {
                    "number": round(position.get("takeProfit", 0), 4)
                },
                "Risk:Reward": {
                    "number": round(position.get("riskReward", 0), 2)
                },
                "Mode": {
                    "select": {"name": execution.get("mode", "PAPER")}
                },
                "Timestamp": {
                    "date": {"start": datetime.utcnow().isoformat()}
                }
            }
            
            page = self.client.pages.create(
                parent={"database_id": self.databases.get("executions", "")},
                properties=properties
            )
            
            return page.get("id")
        except Exception as e:
            logger.error(f"Error logging execution to Notion: {e}", exc_info=True)
            return None

    def log_daily_stats(self, stats: Dict[str, Any]) -> Optional[str]:
        """
        Log daily statistics to Notion
        
        Args:
            stats: Statistics dictionary
            
        Returns:
            Page ID if successful, None otherwise
        """
        try:
            properties = {
                "Date": {
                    "date": {"start": datetime.utcnow().isoformat()}
                },
                "Execution Time": {
                    "number": stats.get("executionTime", 0)
                },
                "API Calls": {
                    "number": stats.get("apiCalls", 0)
                },
                "Success Rate": {
                    "number": round(stats.get("successRate", 0), 4)
                },
                "Errors": {
                    "number": stats.get("errors", 0)
                },
                "Avg Execution Time": {
                    "number": stats.get("avgExecutionTime", 0)
                }
            }
            
            page = self.client.pages.create(
                parent={"database_id": self.databases.get("dailyStats", "")},
                properties=properties
            )
            
            return page.get("id")
        except Exception as e:
            logger.error(f"Error logging daily stats to Notion: {e}", exc_info=True)
            return None

