"""Health Check and Monitoring"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class HealthChecker:
    """Health check system for trading bot"""
    
    def __init__(self):
        """Initialize Health Checker"""
        self.checks: Dict[str, Any] = {}
        self.last_check_time: Optional[datetime] = None
    
    def check_api_health(self, bybit_client: Any) -> Dict[str, Any]:
        """
        Check Bybit API health
        
        Args:
            bybit_client: BybitClient instance
            
        Returns:
            Health check result
        """
        try:
            # Try to fetch tickers (public endpoint)
            tickers = bybit_client.get_tickers(category="linear")
            return {
                "status": "healthy",
                "endpoint": "bybit_api",
                "response_time": "<1s",  # Could measure actual time
                "data_points": len(tickers) if tickers else 0
            }
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return {
                "status": "unhealthy",
                "endpoint": "bybit_api",
                "error": str(e)
            }
    
    def check_database_health(self, database: Any) -> Dict[str, Any]:
        """
        Check database health
        
        Args:
            database: Database instance
            
        Returns:
            Health check result
        """
        try:
            # Try to query trades table
            cursor = database.execute("SELECT COUNT(*) FROM trades LIMIT 1")
            count = cursor.fetchone()[0]
            return {
                "status": "healthy",
                "endpoint": "database",
                "total_trades": count
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "endpoint": "database",
                "error": str(e)
            }
    
    def check_position_tracker_health(self, position_tracker: Any) -> Dict[str, Any]:
        """
        Check position tracker health
        
        Args:
            position_tracker: PositionTracker instance
            
        Returns:
            Health check result
        """
        try:
            open_positions = position_tracker.get_open_positions()
            stats = position_tracker.get_position_stats()
            return {
                "status": "healthy",
                "endpoint": "position_tracker",
                "open_positions": len(open_positions),
                "stats": stats
            }
        except Exception as e:
            logger.error(f"Position tracker health check failed: {e}")
            return {
                "status": "unhealthy",
                "endpoint": "position_tracker",
                "error": str(e)
            }
    
    def run_all_checks(
        self,
        bybit_client: Optional[Any] = None,
        database: Optional[Any] = None,
        position_tracker: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Run all health checks
        
        Args:
            bybit_client: BybitClient instance (optional)
            database: Database instance (optional)
            position_tracker: PositionTracker instance (optional)
            
        Returns:
            Dictionary with all health check results
        """
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy",
            "checks": {}
        }
        
        if bybit_client:
            api_check = self.check_api_health(bybit_client)
            results["checks"]["api"] = api_check
            if api_check["status"] != "healthy":
                results["overall_status"] = "degraded"
        
        if database:
            db_check = self.check_database_health(database)
            results["checks"]["database"] = db_check
            if db_check["status"] != "healthy":
                results["overall_status"] = "unhealthy"
        
        if position_tracker:
            pos_check = self.check_position_tracker_health(position_tracker)
            results["checks"]["position_tracker"] = pos_check
            if pos_check["status"] != "healthy":
                results["overall_status"] = "degraded"
        
        self.last_check_time = datetime.utcnow()
        return results
    
    def is_healthy(self, check_results: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if system is healthy
        
        Args:
            check_results: Optional health check results (runs checks if not provided)
            
        Returns:
            True if healthy, False otherwise
        """
        if check_results is None:
            # Would need to pass components to run checks
            return False
        
        return check_results.get("overall_status") == "healthy"

