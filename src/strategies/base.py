"""Base Strategy Class"""

from abc import ABC, abstractmethod
from typing import List, Optional
import logging

from events.market_event import MarketEvent
from events.signal_event import SignalEvent
from events.fill_event import FillEvent
from events.position_update_event import PositionUpdateEvent

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """
    Base class for all trading strategies.
    
    Strategies are isolated modules that generate signals based on market events.
    They must not maintain their own trading state.
    """
    
    def __init__(self, name: str, config: dict) -> None:
        """
        Initialize strategy.
        
        Args:
            name: Strategy name
            config: Strategy configuration
        """
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self.logger.info(f"Strategy {name} initialized")
    
    @abstractmethod
    def generate_signals(self, market_event: MarketEvent) -> List[SignalEvent]:
        """
        Generate trading signals from market event.
        
        Args:
            market_event: Market data event
            
        Returns:
            List of SignalEvent objects (can be empty)
        """
        pass
    
    def on_fill(self, fill_event: FillEvent) -> None:
        """
        Called when a fill event occurs.
        
        Override this to handle position fills (e.g., update internal state).
        
        Args:
            fill_event: Fill event
        """
        pass
    
    def on_position_update(self, position_event: PositionUpdateEvent) -> None:
        """
        Called when position is updated.
        
        Override this to handle position updates (e.g., exits, modifications).
        
        Args:
            position_event: Position update event
        """
        pass
    
    def is_enabled(self) -> bool:
        """Check if strategy is enabled"""
        return self.config.get("enabled", True)

