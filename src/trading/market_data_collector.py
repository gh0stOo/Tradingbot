"""Market Data Collector for Event-Driven Architecture"""

import logging
from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import datetime

from events.market_event import MarketEvent
from trading.market_data import MarketData
from integrations.bybit import BybitClient

logger = logging.getLogger(__name__)


class MarketDataCollector:
    """
    Collects market data and publishes MarketEvents.
    
    Integrates with existing MarketData class and publishes events.
    """
    
    def __init__(
        self,
        market_data: MarketData,
        event_publisher: Optional[Any] = None  # EventLoop or function
    ) -> None:
        """
        Initialize market data collector.
        
        Args:
            market_data: MarketData instance
            event_publisher: Function to publish events (event_loop.publish_event)
        """
        self.market_data = market_data
        self.event_publisher = event_publisher
        logger.info("MarketDataCollector initialized")
    
    def collect_and_publish(self, symbols: List[str]) -> List[MarketEvent]:
        """
        Collect market data for symbols and publish MarketEvents.
        
        Args:
            symbols: List of trading symbols
            
        Returns:
            List of MarketEvent objects
        """
        events: List[MarketEvent] = []
        
        for symbol in symbols:
            try:
                # Get symbol data with klines
                symbol_data = self.market_data.get_symbol_data(
                    symbol=symbol,
                    intervals=[1, 5, 15],  # 1m, 5m, 15m
                    limit=100
                )
                
                if not symbol_data:
                    continue
                
                # Get current price
                ticker = symbol_data.get("ticker")
                if not ticker:
                    continue
                
                current_price = Decimal(str(ticker.get("lastPrice", 0)))
                if current_price <= 0:
                    continue
                
                # Prepare klines for strategies
                klines_m1 = symbol_data.get("klines", {}).get("1", [])
                klines_m5 = symbol_data.get("klines", {}).get("5", [])
                
                # Create market event
                market_event = MarketEvent(
                    symbol=symbol,
                    price=current_price,
                    volume=Decimal(str(ticker.get("volume24h", 0))),
                    timestamp=datetime.utcnow().isoformat(),
                    bid=Decimal(str(ticker.get("bid1Price", current_price))),
                    ask=Decimal(str(ticker.get("ask1Price", current_price))),
                    open_24h=Decimal(str(ticker.get("openPrice", current_price))),
                    high_24h=Decimal(str(ticker.get("highPrice24h", current_price))),
                    low_24h=Decimal(str(ticker.get("lowPrice24h", current_price))),
                    volume_24h=Decimal(str(ticker.get("volume24h", 0))),
                    additional_data={
                        "klines_m1": klines_m1,
                        "klines_m5": klines_m5,
                        "symbol_info": symbol_data.get("symbol_info", {}),
                    },
                    source="MarketDataCollector",
                )
                
                events.append(market_event)
                
                # Publish event if publisher available
                if self.event_publisher:
                    self.event_publisher(market_event)
            
            except Exception as e:
                logger.error(f"Error collecting data for {symbol}: {e}", exc_info=True)
        
        return events

