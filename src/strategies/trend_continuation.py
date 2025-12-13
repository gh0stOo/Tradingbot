"""Intraday Trend Continuation Strategy"""

from typing import List
from decimal import Decimal
import pandas as pd
from events.market_event import MarketEvent
from events.signal_event import SignalEvent
from strategies.base import BaseStrategy
from trading.indicators import Indicators
from trading.regime_detector import RegimeDetector


class TrendContinuationStrategy(BaseStrategy):
    """
    Intraday Trend Continuation Strategy.
    
    Entry: Higher-Timeframe Trend + Pullback + Volatility Reset
    Exit: Trend-End Signal, Profit Target, Stop-Loss
    """
    
    def __init__(self, config: dict) -> None:
        """Initialize Trend Continuation Strategy"""
        super().__init__("trend_continuation", config)
        self.indicators = Indicators(enable_cache=True)
        self.regime_detector = RegimeDetector()
        
        # Strategy parameters
        self.config = config.get("trendContinuation", {})
        self.pullback_threshold = self.config.get("pullbackThreshold", 0.015)  # 1.5% pullback
        self.volatility_reset_ratio = self.config.get("volatilityResetRatio", 0.60)  # 60% of move range
        self.min_confidence = self.config.get("minConfidence", 0.70)
    
    def generate_signals(self, market_event: MarketEvent) -> List[SignalEvent]:
        """
        Generate signals from market event.
        
        Requires:
        - Higher-Timeframe Trend detected
        - Pullback within trend
        - Volatility Reset (low volatility before continuation)
        """
        if not self.is_enabled():
            return []
        
        if not market_event.additional_data:
            return []
        
        # Need both 1m and 5m (higher timeframe) data
        klines_m1 = market_event.additional_data.get("klines_m1")
        klines_m5 = market_event.additional_data.get("klines_m5")
        
        if klines_m1 is None or len(klines_m1) < 50:
            return []
        
        if klines_m5 is None or len(klines_m5) < 20:
            return []
        
        try:
            df_m1 = self.indicators.parse_klines(klines_m1)
            df_m5 = self.indicators.parse_klines(klines_m5)
            
            if len(df_m1) < 50 or len(df_m5) < 20:
                return []
            
            # Detect Higher-Timeframe Trend (5m)
            indicators_m5 = self.indicators.calculate_all(df_m5)
            if not indicators_m5:
                return []
            
            ema21_m5 = indicators_m5.get("ema21", 0)
            ema50_m5 = indicators_m5.get("ema50", 0)
            current_price_m5 = df_m5["close"].iloc[-1]
            
            # Higher timeframe trend: Price > EMA21 > EMA50 (bullish) or Price < EMA21 < EMA50 (bearish)
            is_htf_bullish = current_price_m5 > ema21_m5 > ema50_m5
            is_htf_bearish = current_price_m5 < ema21_m5 < ema50_m5
            
            if not (is_htf_bullish or is_htf_bearish):
                return []  # No clear HTF trend
            
            # Check for Pullback on 1m
            current_price = Decimal(str(market_event.price))
            
            # Recent high/low for pullback detection
            recent_lookback = 20
            recent_high = df_m1["high"].iloc[-recent_lookback:].max()
            recent_low = df_m1["low"].iloc[-recent_lookback:].min()
            
            # Pullback in uptrend: price pulled back from recent high
            # Pullback in downtrend: price pulled back from recent low
            pullback_size = Decimal("0")
            is_pullback = False
            
            if is_htf_bullish:
                # Uptrend: look for pullback from high
                pullback_size = (recent_high - current_price) / recent_high
                is_pullback = pullback_size >= self.pullback_threshold and pullback_size < 0.05  # 1.5% - 5%
            elif is_htf_bearish:
                # Downtrend: look for pullback from low
                pullback_size = (current_price - recent_low) / recent_low
                is_pullback = pullback_size >= self.pullback_threshold and pullback_size < 0.05
            
            if not is_pullback:
                return []
            
            # Check for Volatility Reset
            # Recent volatility should be lower than the move that preceded it
            indicators_m1 = self.indicators.calculate_all(df_m1)
            if not indicators_m1:
                return []
            
            # Recent range (last 5 bars)
            recent_range = df_m1["high"].iloc[-5:].max() - df_m1["low"].iloc[-5:].min()
            
            # Move range (bars 10-20 before recent)
            if len(df_m1) >= 25:
                move_range = df_m1["high"].iloc[-25:-5].max() - df_m1["low"].iloc[-25:-5].min()
            else:
                move_range = recent_range * Decimal("2")
            
            if move_range <= 0:
                return []
            
            volatility_ratio = float(recent_range) / move_range
            is_reset = volatility_ratio <= self.volatility_reset_ratio  # Recent < 60% of move
            
            if not is_reset:
                return []
            
            signals: List[SignalEvent] = []
            atr = indicators_m1.get("atr", 0)
            
            if atr <= 0:
                return []
            
            # Generate signal in trend direction
            if is_htf_bullish:
                # Uptrend continuation: Buy on pullback
                confidence = min(0.90, 0.70 + (pullback_size - self.pullback_threshold) * 5.0)
                if confidence >= self.min_confidence:
                    sl_distance = Decimal(str(atr)) * Decimal("2.0")
                    tp_distance = sl_distance * Decimal("3.0")  # 3R target
                    
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
                        reasoning=f"Trend continuation: HTF uptrend + Pullback ({pullback_size*100:.2f}%) + Volatility reset ({volatility_ratio:.2f})",
                        source=f"{self.name}_strategy",
                        metadata={
                            "htf_trend": "bullish",
                            "pullback_pct": float(pullback_size * 100),
                            "volatility_ratio": float(volatility_ratio),
                        }
                    )
                    signals.append(signal)
            
            elif is_htf_bearish:
                # Downtrend continuation: Sell on pullback
                confidence = min(0.90, 0.70 + (pullback_size - self.pullback_threshold) * 5.0)
                if confidence >= self.min_confidence:
                    sl_distance = Decimal(str(atr)) * Decimal("2.0")
                    tp_distance = sl_distance * Decimal("3.0")
                    
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
                        reasoning=f"Trend continuation: HTF downtrend + Pullback ({pullback_size*100:.2f}%) + Volatility reset ({volatility_ratio:.2f})",
                        source=f"{self.name}_strategy",
                        metadata={
                            "htf_trend": "bearish",
                            "pullback_pct": float(pullback_size * 100),
                            "volatility_ratio": float(volatility_ratio),
                        }
                    )
                    signals.append(signal)
            
            return signals
        
        except Exception as e:
            self.logger.error(f"Error generating trend continuation signals: {e}", exc_info=True)
            return []

