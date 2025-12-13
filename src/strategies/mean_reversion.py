"""Crypto Mean Reversion Strategy (Liquidation Fade)"""

from typing import List
from decimal import Decimal
import pandas as pd
from events.market_event import MarketEvent
from events.signal_event import SignalEvent
from strategies.base import BaseStrategy
from trading.indicators import Indicators
from trading.regime_detector import RegimeDetector


class MeanReversionStrategy(BaseStrategy):
    """
    Crypto Mean Reversion Strategy (Liquidation Fade).
    
    Entry: Fast Move + Volume Climax + Volatility Collapse
    Exit: Very short Time-Stop (30-60 min), Conservative Profit Target
    """
    
    def __init__(self, config: dict) -> None:
        """Initialize Mean Reversion Strategy"""
        super().__init__("mean_reversion", config)
        self.indicators = Indicators(enable_cache=True)
        self.regime_detector = RegimeDetector()
        
        # Strategy parameters
        self.config = config.get("meanReversion", {})
        self.fast_move_threshold = self.config.get("fastMoveThreshold", 0.03)  # 3% move
        self.volume_climax_ratio = self.config.get("volumeClimaxRatio", 2.0)  # 2x avg volume
        self.max_hold_minutes = self.config.get("maxHoldMinutes", 60)
        self.min_confidence = self.config.get("minConfidence", 0.60)
    
    def generate_signals(self, market_event: MarketEvent) -> List[SignalEvent]:
        """
        Generate signals from market event.
        
        Requires:
        - Fast Move (strong price movement)
        - Volume Climax (high volume)
        - Volatility Collapse (low volatility after move)
        """
        if not self.is_enabled():
            return []
        
        if not market_event.additional_data or "klines_m1" not in market_event.additional_data:
            return []
        
        klines_m1 = market_event.additional_data.get("klines_m1")
        if klines_m1 is None or len(klines_m1) < 30:
            return []
        
        try:
            df = self.indicators.parse_klines(klines_m1)
            if len(df) < 30:
                return []
            
            # Calculate indicators
            indicators_dict = self.indicators.calculate_all(df)
            if not indicators_dict:
                return []
            
            current_price = Decimal(str(market_event.price))
            current_volume = Decimal(str(market_event.volume))
            
            # Check for Fast Move
            lookback_10 = 10
            price_10_bars_ago = df["close"].iloc[-lookback_10]
            price_change = abs(current_price - price_10_bars_ago) / price_10_bars_ago
            
            if price_change < self.fast_move_threshold:
                return []  # Not a fast move
            
            # Check for Volume Climax
            avg_volume = df["volume"].iloc[-20:].mean()
            if avg_volume <= 0:
                return []
            
            volume_ratio = float(current_volume) / avg_volume
            if volume_ratio < self.volume_climax_ratio:
                return []  # Not a volume climax
            
            # Check for Volatility Collapse (after the fast move)
            # Look at recent volatility vs. move volatility
            recent_high = df["high"].iloc[-5:].max()
            recent_low = df["low"].iloc[-5:].min()
            recent_range = recent_high - recent_low
            
            move_high = df["high"].iloc[-lookback_10:].max()
            move_low = df["low"].iloc[-lookback_10:].min()
            move_range = move_high - move_low
            
            # Volatility collapse = recent range is much smaller than move range
            if move_range <= 0:
                return []
            
            volatility_ratio = float(recent_range) / move_range
            is_collapse = volatility_ratio < 0.40  # Recent range < 40% of move range
            
            if not is_collapse:
                return []
            
            signals: List[SignalEvent] = []
            
            # Determine direction: Fade the fast move
            is_up_move = current_price > price_10_bars_ago
            
            # Bullish fade: Fast move down → Mean reversion up
            if not is_up_move:
                # Fast move down, fade it (buy signal)
                confidence = min(0.85, 0.60 + (price_change - self.fast_move_threshold) * 2.0)
                if confidence >= self.min_confidence:
                    # Very tight stop (1 ATR) and conservative target (1.5 R)
                    atr = indicators_dict.get("atr", 0)
                    if atr > 0:
                        sl_distance = Decimal(str(atr)) * Decimal("1.0")
                        tp_distance = sl_distance * Decimal("1.5")  # Conservative 1.5R
                        
                        stop_loss = current_price - sl_distance
                        take_profit = current_price + tp_distance  # Fade down move → buy
                        
                        signal = SignalEvent(
                            symbol=market_event.symbol,
                            side="Buy",
                            strategy_name=self.name,
                            entry_price=current_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            confidence=float(confidence),
                            reasoning=f"Mean reversion fade: Fast move down ({price_change*100:.2f}%) + Volume climax ({volume_ratio:.2f}x) + Volatility collapse",
                            source=f"{self.name}_strategy",
                            metadata={
                                "fast_move_pct": float(price_change * 100),
                                "volume_ratio": float(volume_ratio),
                                "volatility_ratio": float(volatility_ratio),
                                "max_hold_minutes": self.max_hold_minutes,
                            }
                        )
                        signals.append(signal)
            
            # Bearish fade: Fast move up → Mean reversion down
            else:
                # Fast move up, fade it (sell signal)
                confidence = min(0.85, 0.60 + (price_change - self.fast_move_threshold) * 2.0)
                if confidence >= self.min_confidence:
                    atr = indicators_dict.get("atr", 0)
                    if atr > 0:
                        sl_distance = Decimal(str(atr)) * Decimal("1.0")
                        tp_distance = sl_distance * Decimal("1.5")
                        
                        stop_loss = current_price + sl_distance
                        take_profit = current_price - tp_distance  # Fade up move → sell
                        
                        signal = SignalEvent(
                            symbol=market_event.symbol,
                            side="Sell",
                            strategy_name=self.name,
                            entry_price=current_price,
                            stop_loss=stop_loss,
                            take_profit=take_profit,
                            confidence=float(confidence),
                            reasoning=f"Mean reversion fade: Fast move up ({price_change*100:.2f}%) + Volume climax ({volume_ratio:.2f}x) + Volatility collapse",
                            source=f"{self.name}_strategy",
                            metadata={
                                "fast_move_pct": float(price_change * 100),
                                "volume_ratio": float(volume_ratio),
                                "volatility_ratio": float(volatility_ratio),
                                "max_hold_minutes": self.max_hold_minutes,
                            }
                        )
                        signals.append(signal)
            
            return signals
        
        except Exception as e:
            self.logger.error(f"Error generating mean reversion signals: {e}", exc_info=True)
            return []

