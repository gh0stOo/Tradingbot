"""Intraday Volatility Expansion Strategy"""

from typing import List, Optional
import pandas as pd
from events.market_event import MarketEvent
from events.signal_event import SignalEvent
from strategies.base import BaseStrategy
from trading.indicators import Indicators
from trading.regime_detector import RegimeDetector


class VolatilityExpansionStrategy(BaseStrategy):
    """
    Intraday Volatility Expansion Strategy (Premium).
    
    Entry: Volatility Compression Regime → Range Break + Volatility Spike
    Exit: R-Multiple based, Time-Stop (EOD), Volatility Collapse
    """
    
    def __init__(self, config: dict) -> None:
        """Initialize Volatility Expansion Strategy"""
        super().__init__("volatility_expansion", config)
        self.indicators = Indicators(enable_cache=True)
        self.regime_detector = RegimeDetector()
        
        # Strategy parameters
        self.config = config.get("volatilityExpansion", {})
        self.compression_lookback = self.config.get("compressionLookback", 20)
        # Temporarily reduced thresholds for testing
        self.expansion_threshold = self.config.get("expansionThreshold", 1.2)  # 1.2x ATR (reduced from 1.5x)
        self.r_multiple_target = self.config.get("rMultipleTarget", 2.5)
        self.min_confidence = self.config.get("minConfidence", 0.50)  # 50% (reduced from 65%)
    
    def generate_signals(self, market_event: MarketEvent) -> List[SignalEvent]:
        """
        Generate signals from market event.
        
        Requires:
        - Volatility Compression Regime detected
        - Range Break with Volatility Spike
        """
        if not self.is_enabled():
            return []
        
        # Need historical data - if not available in event, return empty
        if not market_event.additional_data or "klines_m1" not in market_event.additional_data:
            return []
        
        klines_m1 = market_event.additional_data.get("klines_m1")
        if klines_m1 is None or len(klines_m1) < self.compression_lookback + 10:
            return []
        
        try:
            # Convert to DataFrame
            df = self.indicators.parse_klines(klines_m1)
            if len(df) < self.compression_lookback + 10:
                return []
            
            # Calculate indicators
            indicators_dict = self.indicators.calculate_all(df)
            if not indicators_dict or "atr" not in indicators_dict:
                return []
            
            atr = float(indicators_dict["atr"])
            if atr <= 0:
                return []
            
            current_price = float(market_event.price)
            high = float(df["high"].iloc[-self.compression_lookback:].max())
            low = float(df["low"].iloc[-self.compression_lookback:].min())
            range_size = high - low
            
            # Check for Volatility Compression
            # Compression = low ATR relative to range
            atr_to_range_ratio = atr / range_size if range_size > 0 else 0
            
            # Compression threshold: ATR should be < 30% of range
            is_compression = atr_to_range_ratio < 0.30
            
            if not is_compression:
                return []
            
            # Check for Volatility Expansion + Range Break
            # Compare recent ATR to compression period ATR
            recent_atr = indicators_dict.get("atr", atr)  # Use current ATR
            compression_atr = df["high"].iloc[-self.compression_lookback:].subtract(
                df["low"].iloc[-self.compression_lookback:]
            ).mean()
            
            if compression_atr <= 0:
                return []
            
            expansion_ratio = recent_atr / compression_atr
            is_expansion = expansion_ratio >= self.expansion_threshold
            
            # Check for Range Break
            # Use current_price from market_event (most recent price)
            # For high/low, use the last candle's data (current candle not yet closed)
            # This is acceptable as we're checking for breakouts of the range
            
            # For breakout detection, check if current_price exceeds the range
            # This ensures we use the most recent price, not a potentially stale candle close
            price_breakout_up = current_price > high * 1.001
            price_breakout_down = current_price < low * 0.999
            
            # Also check candle-based breakout for confirmation
            current_high = float(df["high"].iloc[-1]) if len(df) > 0 else current_price
            current_low = float(df["low"].iloc[-1]) if len(df) > 0 else current_price
            candle_breakout_up = current_high > high * 1.001
            candle_breakout_down = current_low < low * 0.999
            
            # Require both price AND candle breakout for confirmation
            is_breakout_up = price_breakout_up and candle_breakout_up
            is_breakout_down = price_breakout_down and candle_breakout_down
            
            signals: List[SignalEvent] = []
            
            # Bullish signal: Compression + Expansion + Upward Breakout
            if is_expansion and is_breakout_up:
                confidence = min(0.9, 0.65 + (expansion_ratio - 1.0) * 0.1)
                if confidence >= self.min_confidence:
                    # Calculate stop loss and take profit (R-Multiple based)
                    sl_distance = atr * 2.0  # 2 ATR stop
                    tp_distance = sl_distance * float(self.r_multiple_target)  # R-Multiple target
                    
                    stop_loss = current_price - sl_distance
                    take_profit = current_price + tp_distance
                    
                    signal = SignalEvent(
                        symbol=market_event.symbol,
                        side="Buy",
                        strategy_name=self.name,
                        entry_price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        confidence=float(confidence),
                        timestamp=market_event.timestamp,  # Set timestamp from market event
                        reasoning=f"Volatility expansion breakout: Compression ({atr_to_range_ratio:.2f}) → Expansion ({expansion_ratio:.2f}x)",
                        source=f"{self.name}_strategy",
                        metadata={
                            "expansion_ratio": float(expansion_ratio),
                            "compression_ratio": float(atr_to_range_ratio),
                            "r_multiple": float(self.r_multiple_target),
                        }
                    )
                    signals.append(signal)
            
            # Bearish signal: Compression + Expansion + Downward Breakdown
            elif is_expansion and is_breakout_down:
                confidence = min(0.9, 0.65 + (expansion_ratio - 1.0) * 0.1)
                if confidence >= self.min_confidence:
                    sl_distance = atr * 2.0
                    tp_distance = sl_distance * float(self.r_multiple_target)
                    
                    stop_loss = current_price + sl_distance
                    take_profit = current_price - tp_distance
                    
                    signal = SignalEvent(
                        symbol=market_event.symbol,
                        side="Sell",
                        strategy_name=self.name,
                        entry_price=current_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        confidence=float(confidence),
                        timestamp=market_event.timestamp,  # Set timestamp from market event
                        reasoning=f"Volatility expansion breakdown: Compression ({atr_to_range_ratio:.2f}) → Expansion ({expansion_ratio:.2f}x)",
                        source=f"{self.name}_strategy",
                        metadata={
                            "expansion_ratio": float(expansion_ratio),
                            "compression_ratio": float(atr_to_range_ratio),
                            "r_multiple": float(self.r_multiple_target),
                        }
                    )
                    signals.append(signal)
            
            return signals
        
        except Exception as e:
            self.logger.error(f"Error generating volatility expansion signals: {e}", exc_info=True)
            return []

