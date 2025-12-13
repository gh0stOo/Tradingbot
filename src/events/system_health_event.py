"""System Health Event - Health Checks, Errors"""

from dataclasses import dataclass
from typing import Dict, Optional
from events.event import BaseEvent


@dataclass
class SystemHealthEvent(BaseEvent):
    """
    System health event.
    
    Generated for health checks, errors, warnings, and system status updates.
    """
    
    component: str = ""  # Component name (e.g., "RiskEngine", "OrderExecutor")
    status: str = "healthy"  # "healthy", "warning", "error", "critical"
    message: str = ""
    error_details: Optional[Dict] = None
    metrics: Optional[Dict] = None  # Component-specific metrics
    metadata: Optional[Dict] = None

