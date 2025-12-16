"""Market Regime Detection Module"""

from typing import Dict, Any, Union

class RegimeDetector:
    """Detect market regime: trending, ranging, or volatile"""
    
    @staticmethod
    def detect_regime(
        indicators: Union[Dict[str, float], float],
        price: float,
        volatility_window: int = 20
    ) -> Dict[str, Any]:
        """
        Detect market regime based on indicators
        
        Args:
            indicators: Dictionary with indicator values
            price: Current price
            volatility_window: Window for volatility calculation
            
        Returns:
            Dictionary with regime information
        """
        # Backward compatibility: allow callers to pass adx/atr as first args (legacy tests)
        if not isinstance(indicators, dict):
            # indicators is actually ADX value in legacy signature
            indicators = {"adx": indicators}

        ema21 = indicators.get("ema21", price)
        ema50 = indicators.get("ema50", price)
        adx = indicators.get("adx", 0)
        volatility = indicators.get("volatility", 0)
        rsi = indicators.get("rsi", 50)
        
        # Volatility regime
        avg_volatility = 0.02  # 2% daily average
        is_high_volatility = volatility > avg_volatility * 1.5
        is_low_volatility = volatility < avg_volatility * 0.5
        
        # Trend regime
        price_ema50_diff = abs((price - ema50) / ema50) if ema50 > 0 else 0
        is_trending = price_ema50_diff > 0.03 and adx > 25
        is_ranging = price_ema50_diff < 0.02 and adx < 20
        
        # Direction
        is_bullish = price > ema21 and ema21 > ema50
        is_bearish = price < ema21 and ema21 < ema50
        
        # Momentum
        is_oversold = rsi < 30
        is_overbought = rsi > 70
        has_strong_momentum = rsi > 60 or rsi < 40
        
        # Determine regime type with clear hierarchy
        # First check for trending (ADX-based, independent of volatility)
        if is_trending:  # ADX > 25 and price deviation > 3%
            regime_type = "trending"
        # Then check for volatile (based on volatility alone)
        elif is_high_volatility:  # Volatility > 1.5x average
            regime_type = "volatile"
        # Default to ranging
        else:
            regime_type = "ranging"
        
        return {
            "type": regime_type,
            "isTrending": is_trending,
            "isRanging": is_ranging,
            "isBullish": is_bullish,
            "isBearish": is_bearish,
            "isHighVolatility": is_high_volatility,
            "isOversold": is_oversold,
            "isOverbought": is_overbought,
            "hasStrongMomentum": has_strong_momentum
        }

