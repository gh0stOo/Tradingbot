"""Position Update Event - Position Changed"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional
from events.event import BaseEvent


@dataclass
class PositionUpdateEvent(BaseEvent):
    """
    Position update event.
    
    Generated when a position is opened, closed, or modified.
    """
    
    symbol: str = ""
    side: str = "Buy"  # "Buy" or "Sell"
    quantity: Decimal = Decimal("0")  # Current position size (0 if closed)
    entry_price: Decimal = Decimal("0")
    current_price: Decimal = Decimal("0")
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Optional[Decimal] = None  # Set when position closes
    position_status: str = "open"  # open, closed, partial
    update_type: str = "opened"  # opened, closed, modified, partial_fill
    metadata: Optional[Dict] = None

