"""Kill Switch Event - Emergency Stop"""

from dataclasses import dataclass
from typing import Dict, Optional
from events.event import BaseEvent


@dataclass
class KillSwitchEvent(BaseEvent):
    """
    Kill switch event for emergency stop.
    
    Generated when critical risk limits are breached or manual kill switch is triggered.
    All trading must stop immediately.
    """
    
    reason: str = ""  # Reason for kill switch
    triggered_by: str = ""  # Component that triggered (e.g., "RiskEngine", "Manual")
    severity: str = "critical"  # critical, warning
    auto_recovery: bool = False  # Whether system can auto-recover
    recovery_conditions: Optional[Dict] = None  # Conditions for recovery
    metadata: Optional[Dict] = None

