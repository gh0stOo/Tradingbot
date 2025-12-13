"""Base Event Class for Event-Driven Architecture"""

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
import uuid


@dataclass
class BaseEvent(ABC):
    """
    Base class for all events in the trading system.
    
    All events must inherit from this class and implement the required fields.
    Events are immutable after creation.
    """
    
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = field(default="unknown")
    event_type: str = field(init=False)
    
    def __post_init__(self) -> None:
        """Set event_type based on class name"""
        if not hasattr(self, 'event_type') or self.event_type == "BaseEvent":
            self.event_type = self.__class__.__name__
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization"""
        result: Dict[str, Any] = {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "event_type": self.event_type,
        }
        
        # Add all non-private fields
        for key, value in self.__dict__.items():
            if not key.startswith('_') and key not in result:
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                elif isinstance(value, (int, float, str, bool, type(None))):
                    result[key] = value
                elif hasattr(value, '__dict__'):
                    result[key] = str(value)
                else:
                    result[key] = value
        
        return result
    
    def __repr__(self) -> str:
        """String representation of event"""
        return f"{self.event_type}(id={self.event_id[:8]}, source={self.source}, time={self.timestamp.isoformat()})"

