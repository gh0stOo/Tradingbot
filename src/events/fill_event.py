"""Fill Event - Order Filled/Executed"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Optional
from datetime import datetime
from events.event import BaseEvent


@dataclass
class FillEvent(BaseEvent):
    """
    Order fill/execution event.
    
    Generated when an order is filled (partially or fully).
    Contains actual execution price and quantity.
    """
    
    client_order_id: str = ""
    exchange_order_id: str = ""
    symbol: str = ""
    side: str = "Buy"  # "Buy" or "Sell"
    filled_quantity: Decimal = Decimal("0")
    filled_price: Decimal = Decimal("0")
    fill_time: datetime = field(default_factory=datetime.utcnow)
    is_partial: bool = False
    remaining_quantity: Decimal = Decimal("0")
    commission: Optional[Decimal] = None
    commission_asset: Optional[str] = None
    metadata: Optional[Dict] = None

