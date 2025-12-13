"""Candlestick Pattern Detection"""

import pandas as pd
from typing import Dict, List, Optional, Any

class CandlestickPatterns:
    """Detect candlestick patterns"""
    
    @staticmethod
    def detect_patterns(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Detect candlestick patterns in DataFrame
        
        Args:
            df: DataFrame with columns: open, high, low, close
            
        Returns:
            List of detected patterns
        """
        if df.empty or len(df) < 3:
            return []
        
        patterns = []
        
        # Get last 3 candles for pattern detection
        last_3 = df.tail(3).copy()
        
        # Bullish Engulfing
        if len(last_3) >= 2:
            prev = last_3.iloc[-2]
            curr = last_3.iloc[-1]
            if (prev["close"] < prev["open"] and  # Previous bearish
                curr["close"] > curr["open"] and  # Current bullish
                curr["open"] < prev["close"] and  # Current opens below prev close
                curr["close"] > prev["open"]):    # Current closes above prev open
                patterns.append({
                    "pattern": "bullish_engulfing",
                    "signal": "Buy",
                    "confidence": 0.65
                })
        
        # Bearish Engulfing
        if len(last_3) >= 2:
            prev = last_3.iloc[-2]
            curr = last_3.iloc[-1]
            if (prev["close"] > prev["open"] and  # Previous bullish
                curr["close"] < curr["open"] and  # Current bearish
                curr["open"] > prev["close"] and  # Current opens above prev close
                curr["close"] < prev["open"]):    # Current closes below prev open
                patterns.append({
                    "pattern": "bearish_engulfing",
                    "signal": "Sell",
                    "confidence": 0.65
                })
        
        # Hammer
        if len(last_3) >= 1:
            curr = last_3.iloc[-1]
            body = abs(curr["close"] - curr["open"])
            lower_shadow = min(curr["open"], curr["close"]) - curr["low"]
            upper_shadow = curr["high"] - max(curr["open"], curr["close"])
            total_range = curr["high"] - curr["low"]
            
            if (body < total_range * 0.3 and  # Small body
                lower_shadow > body * 2 and    # Long lower shadow
                upper_shadow < body * 0.5):    # Small upper shadow
                patterns.append({
                    "pattern": "hammer",
                    "signal": "Buy",
                    "confidence": 0.60
                })
        
        # Shooting Star
        if len(last_3) >= 1:
            curr = last_3.iloc[-1]
            body = abs(curr["close"] - curr["open"])
            lower_shadow = min(curr["open"], curr["close"]) - curr["low"]
            upper_shadow = curr["high"] - max(curr["open"], curr["close"])
            total_range = curr["high"] - curr["low"]
            
            if (body < total_range * 0.3 and  # Small body
                upper_shadow > body * 2 and    # Long upper shadow
                lower_shadow < body * 0.5):    # Small lower shadow
                patterns.append({
                    "pattern": "shooting_star",
                    "signal": "Sell",
                    "confidence": 0.60
                })
        
        # Doji
        if len(last_3) >= 1:
            curr = last_3.iloc[-1]
            body = abs(curr["close"] - curr["open"])
            total_range = curr["high"] - curr["low"]
            
            if body < total_range * 0.1:  # Very small body
                patterns.append({
                    "pattern": "doji",
                    "signal": "Hold",
                    "confidence": 0.50
                })
        
        # Three White Soldiers (simplified)
        if len(last_3) >= 3:
            candles = [last_3.iloc[-3], last_3.iloc[-2], last_3.iloc[-1]]
            if all(c["close"] > c["open"] for c in candles):  # All bullish
                if (candles[0]["close"] < candles[1]["close"] < candles[2]["close"]):
                    patterns.append({
                        "pattern": "three_white_soldiers",
                        "signal": "Buy",
                        "confidence": 0.70
                    })
        
        # Three Black Crows (simplified)
        if len(last_3) >= 3:
            candles = [last_3.iloc[-3], last_3.iloc[-2], last_3.iloc[-1]]
            if all(c["close"] < c["open"] for c in candles):  # All bearish
                if (candles[0]["close"] > candles[1]["close"] > candles[2]["close"]):
                    patterns.append({
                        "pattern": "three_black_crows",
                        "signal": "Sell",
                        "confidence": 0.70
                    })
        
        return patterns

